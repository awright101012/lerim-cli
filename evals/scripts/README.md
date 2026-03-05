# Eval Scripts

Standalone benchmark and utility scripts for Lerim evals.

## bench_ollama.sh

Compare tokens/second, memory usage, and model metadata across Ollama models.
Useful for choosing which local model to use in Lerim eval configs.

### Requirements

`ollama`, `jq`, `curl`, `bc` (all standard on macOS/Linux).

### Usage

```bash
# Default: benchmarks a predefined set of Qwen 3.5 + GLM models
./evals/scripts/bench_ollama.sh

# Benchmark specific models
./evals/scripts/bench_ollama.sh qwen3.5:4b-q8_0 qwen3.5:9b-q8_0

# Control thinking mode and number of runs
THINKING=off NUM_RUNS=5 ./evals/scripts/bench_ollama.sh

# Custom prompt
BENCH_PROMPT="Explain quantum computing" THINKING=off NUM_RUNS=3 ./evals/scripts/bench_ollama.sh
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `BENCH_PROMPT` | A Python binary search prompt | The prompt sent to each model |
| `NUM_RUNS` | `3` | Runs per model (results are averaged) |
| `THINKING` | `off` | `on` or `off` -- prepends `/think` or `/no_think` to the prompt |

### What it measures

For each model:

- **Gen tok/s** -- generation (decode) throughput, including thinking tokens
- **Prompt tok/s** -- prompt evaluation (prefill) throughput
- **Token count** -- total tokens generated per run
- **Timing** -- total wall time, generation time, prefill time per run
- **Memory** -- Ollama RSS before/after loading, system RAM delta, VRAM usage
- **Model info** -- parameter count, quantization level, context length, GPU offload %

Models are unloaded between runs to get clean memory baselines. A warm-up run
loads the model before timed runs start.

### Output

Per-model detailed runs followed by a summary table:

```
║ Model                  │ Params │ Quant  │ VRAM   │ RSS      │ RAM +/- │ Gen tok/s  │ Prompt t/s │
║ qwen3.5:4b-q8_0       │ 4.6B   │ Q8_0   │ 5.31G  │ 5.42G   │ +5.12G  │ 52.60      │ 312.40     │
║ qwen3.5:9b-q8_0       │ 9.1B   │ Q8_0   │ 9.88G  │ 10.12G  │ +9.80G  │ 28.31      │ 187.22     │
```
