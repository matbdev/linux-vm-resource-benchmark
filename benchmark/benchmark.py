#!/usr/bin/env python3
"""Benchmark controlado de FFmpeg para comparação entre VMs Linux.

Fluxo recomendado:
  1) No host, gere UMA única entrada:
       python3 benchmark.py prepare-input --output benchmark_input.mp4
  2) Copie benchmark.py e benchmark_input.mp4 (mesmo arquivo) para cada VM.
  3) Em cada VM, execute:
       python3 benchmark.py run --family debian --distribution debian --vm debian

Por padrão, o comando `run` executa 2 aquecimentos (descartados da amostra)
e 10 execuções válidas, coletando métricas a cada 1 segundo.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    print(
        "Erro: o pacote 'psutil' não está instalado.\n"
        "Instale com: python3 -m pip install psutil",
        file=sys.stderr,
    )
    raise SystemExit(2)

MIB = 1024 * 1024


RAW_FIELDS = [
    "elapsed_s",
    "process_cpu_percent",
    "system_cpu_percent",
    "process_rss_mb",
    "system_memory_used_mb",
    "system_memory_percent",
    "logical_read_mb",
    "logical_write_mb",
    "logical_read_rate_mb_s",
    "logical_write_rate_mb_s",
    "storage_read_mb",
    "storage_write_mb",
    "threads",
    "load_1m",
]

SUMMARY_FIELDS = [
    "family",
    "distribution",
    "vm",
    "run",
    "started_at_utc",
    "input_sha256",
    "elapsed_s",
    "samples",
    "process_cpu_mean_percent",
    "process_cpu_peak_percent",
    "system_cpu_mean_percent",
    "system_cpu_peak_percent",
    "process_rss_mean_mb",
    "process_rss_peak_mb",
    "system_memory_used_mean_mb",
    "system_memory_used_peak_mb",
    "logical_read_total_mb",
    "logical_write_total_mb",
    "storage_read_total_mb",
    "storage_write_total_mb",
    "threads_mean",
    "threads_peak",
    "ffmpeg_exit_code",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_os_release() -> dict[str, str]:
    result: dict[str, str] = {}
    path = Path("/etc/os-release")
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key] = value.strip().strip('"')
    return result


def first_line(command: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    except OSError:
        return None
    out = (proc.stdout or "").strip().splitlines()
    return out[0] if out else None


def system_metadata() -> dict[str, Any]:
    os_release = parse_os_release()
    vm = psutil.virtual_memory()
    return {
        "captured_at_utc": utc_now_iso(),
        "os_pretty_name": os_release.get("PRETTY_NAME"),
        "os_id": os_release.get("ID"),
        "os_version_id": os_release.get("VERSION_ID"),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "memory_total_mb": round(vm.total / MIB, 2),
        "ffmpeg_version": first_line(["ffmpeg", "-version"]),
    }


def require_ffmpeg_and_x264() -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("Erro: 'ffmpeg' não foi encontrado no PATH.")

    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if "libx264" not in (proc.stdout or ""):
        raise SystemExit(
            "Erro: esta instalação do FFmpeg não possui o encoder libx264.\n"
            "Instale uma build do FFmpeg com suporte a libx264 antes do experimento."
        )


def prepare_input(args: argparse.Namespace) -> None:
    require_ffmpeg_and_x264()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    filter_spec = f"testsrc2=size={args.width}x{args.height}:rate={args.fps}"
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        filter_spec,
        "-t",
        str(args.duration),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(output),
    ]

    print(f"Gerando arquivo de entrada padronizado: {output}")
    subprocess.run(cmd, check=True)
    digest = sha256_file(output)
    print(f"SHA-256: {digest}")
    print(
        "Copie ESTE MESMO arquivo para todas as VMs. "
        "O comando 'run' verificará e registrará o hash."
    )


def io_values(proc: psutil.Process) -> tuple[float, float, float, float]:
    """Retorna I/O lógico e físico cumulativo em MiB.

    read_chars/write_chars representam bytes solicitados pelo processo e são menos
    sensíveis ao page cache. read_bytes/write_bytes refletem I/O efetivamente
    contabilizado pelo kernel para armazenamento e podem variar com cache/writeback.
    """
    try:
        io = proc.io_counters()
    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
        return (math.nan, math.nan, math.nan, math.nan)

    logical_read = float(getattr(io, "read_chars", getattr(io, "read_bytes", 0))) / MIB
    logical_write = float(getattr(io, "write_chars", getattr(io, "write_bytes", 0))) / MIB
    storage_read = float(getattr(io, "read_bytes", 0)) / MIB
    storage_write = float(getattr(io, "write_bytes", 0)) / MIB
    return logical_read, logical_write, storage_read, storage_write


def safe_mean(values: list[float]) -> float:
    vals = [v for v in values if not math.isnan(v)]
    return statistics.fmean(vals) if vals else math.nan


def safe_max(values: list[float]) -> float:
    vals = [v for v in values if not math.isnan(v)]
    return max(vals) if vals else math.nan


def round_or_blank(value: float, digits: int = 3) -> float | str:
    return "" if math.isnan(value) else round(value, digits)


def write_raw_csv(path: Path, samples: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RAW_FIELDS)
        writer.writeheader()
        for row in samples:
            writer.writerow({k: round_or_blank(float(row[k])) for k in RAW_FIELDS})


def append_summary(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def collect_process(
    popen: subprocess.Popen[str],
    interval: float,
) -> tuple[list[dict[str, float]], float, str]:
    proc = psutil.Process(popen.pid)

    # Primeira chamada inicializa os contadores de CPU do psutil.
    proc.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None)

    initial_io = io_values(proc)
    prev_io = initial_io
    prev_t = time.monotonic()
    start_t = prev_t
    samples: list[dict[str, float]] = []

    while popen.poll() is None:
        time.sleep(interval)
        now = time.monotonic()
        dt = max(now - prev_t, 1e-9)

        try:
            process_cpu = proc.cpu_percent(interval=None)
            system_cpu = psutil.cpu_percent(interval=None)
            rss_mb = proc.memory_info().rss / MIB
            mem = psutil.virtual_memory()
            system_used_mb = (mem.total - mem.available) / MIB
            current_io = io_values(proc)
            threads = float(proc.num_threads())
            load_1m = float(os.getloadavg()[0]) if hasattr(os, "getloadavg") else math.nan
        except psutil.NoSuchProcess:
            break

        logical_read_rate = (
            (current_io[0] - prev_io[0]) / dt
            if not math.isnan(current_io[0]) and not math.isnan(prev_io[0])
            else math.nan
        )
        logical_write_rate = (
            (current_io[1] - prev_io[1]) / dt
            if not math.isnan(current_io[1]) and not math.isnan(prev_io[1])
            else math.nan
        )

        samples.append(
            {
                "elapsed_s": now - start_t,
                "process_cpu_percent": process_cpu,
                "system_cpu_percent": system_cpu,
                "process_rss_mb": rss_mb,
                "system_memory_used_mb": system_used_mb,
                "system_memory_percent": mem.percent,
                "logical_read_mb": current_io[0] - initial_io[0],
                "logical_write_mb": current_io[1] - initial_io[1],
                "logical_read_rate_mb_s": logical_read_rate,
                "logical_write_rate_mb_s": logical_write_rate,
                "storage_read_mb": current_io[2] - initial_io[2],
                "storage_write_mb": current_io[3] - initial_io[3],
                "threads": threads,
                "load_1m": load_1m,
            }
        )
        prev_io = current_io
        prev_t = now

    elapsed = time.monotonic() - start_t
    _, stderr = popen.communicate()
    return samples, elapsed, stderr or ""


def summary_from_samples(
    *,
    family: str,
    distribution: str,
    vm: str,
    run_number: int,
    started_at: str,
    input_sha256: str,
    elapsed: float,
    samples: list[dict[str, float]],
    exit_code: int,
) -> dict[str, Any]:
    def series(key: str) -> list[float]:
        return [float(s[key]) for s in samples]

    last = samples[-1] if samples else {}
    return {
        "family": family,
        "distribution": distribution,
        "vm": vm,
        "run": run_number,
        "started_at_utc": started_at,
        "input_sha256": input_sha256,
        "elapsed_s": round(elapsed, 3),
        "samples": len(samples),
        "process_cpu_mean_percent": round_or_blank(safe_mean(series("process_cpu_percent"))),
        "process_cpu_peak_percent": round_or_blank(safe_max(series("process_cpu_percent"))),
        "system_cpu_mean_percent": round_or_blank(safe_mean(series("system_cpu_percent"))),
        "system_cpu_peak_percent": round_or_blank(safe_max(series("system_cpu_percent"))),
        "process_rss_mean_mb": round_or_blank(safe_mean(series("process_rss_mb"))),
        "process_rss_peak_mb": round_or_blank(safe_max(series("process_rss_mb"))),
        "system_memory_used_mean_mb": round_or_blank(safe_mean(series("system_memory_used_mb"))),
        "system_memory_used_peak_mb": round_or_blank(safe_max(series("system_memory_used_mb"))),
        "logical_read_total_mb": round_or_blank(float(last.get("logical_read_mb", math.nan))),
        "logical_write_total_mb": round_or_blank(float(last.get("logical_write_mb", math.nan))),
        "storage_read_total_mb": round_or_blank(float(last.get("storage_read_mb", math.nan))),
        "storage_write_total_mb": round_or_blank(float(last.get("storage_write_mb", math.nan))),
        "threads_mean": round_or_blank(safe_mean(series("threads"))),
        "threads_peak": round_or_blank(safe_max(series("threads"))),
        "ffmpeg_exit_code": exit_code,
    }


def run_one(
    *,
    family: str,
    distribution: str,
    vm: str,
    input_path: Path,
    work_dir: Path,
    interval: float,
    threads: int,
    label: str,
    number: int,
    raw_path: Path,
) -> tuple[dict[str, Any] | None, float]:
    output_path = work_dir / f".benchmark-output-{vm}.mp4"
    if output_path.exists():
        output_path.unlink()

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-threads",
        str(threads),
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]

    print(f"[{label} {number:02d}] iniciando...")
    started_at = utc_now_iso()
    popen = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        cwd=work_dir,
    )
    samples, elapsed, stderr = collect_process(popen, interval)
    exit_code = int(popen.returncode or 0)

    try:
        output_path.unlink(missing_ok=True)
    except OSError:
        pass

    if exit_code != 0:
        print(f"[{label} {number:02d}] FALHOU (exit={exit_code})", file=sys.stderr)
        if stderr.strip():
            print(stderr.strip(), file=sys.stderr)
        raise SystemExit(exit_code)

    write_raw_csv(raw_path, samples)
    print(f"[{label} {number:02d}] concluído em {elapsed:.2f} s; {len(samples)} amostras.")

    if label == "aquecimento":
        return None, elapsed

    digest = sha256_file(input_path)
    summary = summary_from_samples(
        family=family,
        distribution=distribution,
        vm=vm,
        run_number=number,
        started_at=started_at,
        input_sha256=digest,
        elapsed=elapsed,
        samples=samples,
        exit_code=exit_code,
    )
    return summary, elapsed


def run_experiment(args: argparse.Namespace) -> None:
    require_ffmpeg_and_x264()

    expected_family = {
        "debian": "debian",
        "ubuntu": "debian",
        "arch-linux": "arch",
        "endeavouros": "arch",
        "fedora": "fedora",
        "bazzite": "fedora",
    }
    if expected_family[args.distribution] != args.family:
        raise SystemExit(
            f"Combinação inválida: {args.distribution!r} pertence à família "
            f"{expected_family[args.distribution]!r}, não {args.family!r}."
        )

    if args.warmups < 0 or args.runs <= 0:
        raise SystemExit("Use warmups >= 0 e runs > 0.")
    if args.interval <= 0:
        raise SystemExit("O intervalo de coleta deve ser > 0.")
    if args.threads <= 0:
        raise SystemExit("O número de threads deve ser > 0.")

    input_path = Path(args.input).expanduser().resolve()
    work_dir = Path(args.work_dir).expanduser().resolve()
    results_root = Path(args.results_dir).expanduser().resolve()

    if not input_path.exists():
        raise SystemExit(
            f"Arquivo de entrada não encontrado: {input_path}\n"
            "Gere-o uma vez com 'prepare-input' e copie o mesmo arquivo para a VM."
        )
    if not work_dir.exists():
        raise SystemExit(f"Diretório de trabalho não existe: {work_dir}")

    experiment_dir = results_root / args.vm
    warmup_dir = experiment_dir / "warmups"
    run_dir = experiment_dir / "runs"
    summary_path = experiment_dir / "summary.csv"
    metadata_path = experiment_dir / "metadata.json"
    warmup_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    digest = sha256_file(input_path)
    metadata = {
        "experiment": {
            "family": args.family,
            "distribution": args.distribution,
            "vm": args.vm,
            "input_file": str(input_path),
            "input_sha256": digest,
            "warmups": args.warmups,
            "measured_runs": args.runs,
            "sample_interval_s": args.interval,
            "cooldown_s": args.cooldown,
            "ffmpeg_threads": args.threads,
            "ffmpeg_workload": "H.264/libx264, preset=medium, crf=23, sem audio",
            "warmups_in_summary": False,
        },
        "system": system_metadata(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 70)
    print(f"VM: {args.vm} | distribuição: {args.distribution} | família: {args.family}")
    print(f"Entrada: {input_path.name}")
    print(f"SHA-256: {digest}")
    print(f"Aquecimentos: {args.warmups} | execuções válidas: {args.runs}")
    print(f"Coleta: a cada {args.interval:g} s | threads FFmpeg: {args.threads}")
    print(f"Resultados: {experiment_dir}")
    print("=" * 70)

    for i in range(1, args.warmups + 1):
        run_one(
            family=args.family,
            distribution=args.distribution,
            vm=args.vm,
            input_path=input_path,
            work_dir=work_dir,
            interval=args.interval,
            threads=args.threads,
            label="aquecimento",
            number=i,
            raw_path=warmup_dir / f"warmup_{i:02d}.csv",
        )
        if args.cooldown > 0:
            time.sleep(args.cooldown)

    # Evita misturar resultados de uma execução antiga com o lote atual.
    if summary_path.exists():
        backup = summary_path.with_name(
            f"summary_previous_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        summary_path.rename(backup)
        print(f"Resumo anterior preservado em: {backup.name}")

    for i in range(1, args.runs + 1):
        summary, _ = run_one(
            family=args.family,
            distribution=args.distribution,
            vm=args.vm,
            input_path=input_path,
            work_dir=work_dir,
            interval=args.interval,
            threads=args.threads,
            label="execução",
            number=i,
            raw_path=run_dir / f"run_{i:02d}.csv",
        )
        assert summary is not None
        append_summary(summary_path, summary)
        if args.cooldown > 0 and i < args.runs:
            time.sleep(args.cooldown)

    print("=" * 70)
    print("Experimento concluído.")
    print(f"Resumo estatístico por execução: {summary_path}")
    print("Os aquecimentos foram salvos separadamente e NÃO entram no summary.csv.")
    print("=" * 70)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark de FFmpeg com coleta de CPU, RAM, I/O e tempo em VMs Linux."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser(
        "prepare-input",
        help="Gera uma única entrada sintética para copiar para todas as VMs.",
    )
    prep.add_argument("--output", default="benchmark_input.mp4")
    prep.add_argument("--duration", type=int, default=60, help="Duração do vídeo, em segundos.")
    prep.add_argument("--width", type=int, default=1280)
    prep.add_argument("--height", type=int, default=720)
    prep.add_argument("--fps", type=int, default=30)
    prep.set_defaults(func=prepare_input)

    run = sub.add_parser("run", help="Executa o lote completo na VM atual.")
    run.add_argument("--family", required=True, choices=["debian", "arch", "fedora"])
    run.add_argument(
        "--distribution",
        required=True,
        choices=["debian", "ubuntu", "arch-linux", "endeavouros", "fedora", "bazzite"],
        help="Distribuição instalada na VM.",
    )
    run.add_argument("--vm", required=True, help="Identificador da VM, ex.: ubuntu")
    run.add_argument("--input", default="benchmark_input.mp4")
    run.add_argument("--results-dir", default="results")
    run.add_argument(
        "--work-dir",
        default=".",
        help="Diretório em disco onde o FFmpeg cria a saída temporária. Evite /tmp se for tmpfs.",
    )
    run.add_argument("--warmups", type=int, default=2)
    run.add_argument("--runs", type=int, default=10)
    run.add_argument("--interval", type=float, default=1.0)
    run.add_argument("--cooldown", type=float, default=3.0)
    run.add_argument("--threads", type=int, default=4)
    run.set_defaults(func=run_experiment)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
