---
name: ai-engineering-from-scratch
version: 1.0.0
description: >
  First-principles AI Engineering curriculum and engine (542 lessons, 20 phases).
  Covers math foundations, neural networks, attention mechanisms, LLMs, SFT, DPO,
  quantization, RAG, tool calling, agent loops, and multi-agent swarms implemented
  from raw math before frameworks.
tags: [ai-engineering, first-principles, deep-learning, llm, agents, curriculum]
---

# AI Engineering from Scratch (Virtu Integrated)

> **Curriculum Repository**: `external/ai-engineering-from-scratch` (Rohit Ghumare & community)
> **Virtu Engine Adapter**: `virtu_omni.ai_scratch.VirtuAIScratch`
> **Philosophical Spine**: Build from raw math in pure code, then verify with production libraries.

---

## 1. 20-Phase Curriculum Structure

| Phase ID | Slug | Description | Focus Lessons |
| :--- | :--- | :--- | :--- |
| **Phase 00** | `00-setup-and-tooling` | Development environment, Git, Python/TypeScript/Rust setup | Tooling, environments |
| **Phase 01** | `01-math-foundations` | Linear algebra, calculus, probability, autograd, SVD, info theory | Gradients, Jacobians, SVD, Entropy |
| **Phase 02** | `02-ml-fundamentals` | Linear & logistic regression, SVM, decision trees, ensembles | SGD, loss functions, metrics |
| **Phase 03** | `03-deep-learning-core` | Multi-layer perceptrons, backpropagation, optimizers (Adam) | Custom tensor autograd, activations |
| **Phase 04** | `04-computer-vision` | Convolutions, pooling, ResNet, ViT (Vision Transformers) | Conv2d from scratch, patch embeddings |
| **Phase 05** | `05-nlp-foundations` | Tokenizers (BPE, WordPiece), N-grams, Word2Vec, Seq2Seq | Subword tokenization, embeddings |
| **Phase 06** | `06-speech-and-audio` | Mel-spectrograms, STFT, audio encoding, Whisper architecture | Acoustic features, CTC loss |
| **Phase 07** | `07-transformers-deep-dive` | Multi-head attention, RoPE, RMSNorm, SwiGLU, KV caching | Self-attention math, causal masking |
| **Phase 08** | `08-generative-ai` | VAEs, GANs, Diffusion models (DDPM, score matching) | Latent space sampling, denoising |
| **Phase 09** | `09-reinforcement-learning`| MDPs, Q-learning, Policy Gradients, PPO, DPO | Reward modeling, policy loss |
| **Phase 10** | `10-llms-from-scratch` | Causal language modeling, generation loops, pretraining | Logits, temperature, top-k/top-p |
| **Phase 11** | `11-llm-engineering` | SFT, LoRA/QLoRA, quantization (GGUF, AWQ, FP8) | Low-rank updates, weight packing |
| **Phase 12** | `12-multimodal-ai` | Vision-Language Models (CLIP, LLaVA, cross-attention) | Image-text projection layers |
| **Phase 13** | `13-tools-and-protocols` | Model Context Protocol (MCP), Function Calling, JSON schemas | MCP stdio/SSE servers, tool specs |
| **Phase 14** | `14-agent-engineering` | ReAct loop, plan-and-solve, reflection, memory banks | Scratchpad parsing, tool dispatch |
| **Phase 15** | `15-autonomous-systems` | Long-horizon planning, tree search, self-correction | Subgoal trees, error recovery |
| **Phase 16** | `16-multi-agent-swarms` | Supervisor-worker, debate, consensus, handoffs | Agent-to-agent communication |
| **Phase 17** | `17-infrastructure-production`| PagedAttention, continuous batching, vLLM / Triton concepts | KV-cache allocation, throughput |
| **Phase 18** | `18-ethics-safety-alignment`| Guardrails, prompt injection defense, red-teaming | Boundary checking, safety filters |
| **Phase 19** | `19-capstone-projects` | Production-grade autonomous agents and end-to-end models | Capstone implementations |

---

## 2. Interactive Tutor and Commands

- **Onboarding / Placement Diagnostic**:
  - Command: `python scripts/workbuddy_virtu_bridge.py` or skill `start-learning`
  - Generates `LEARNING.md` tracking user/agent progress.
- **Interactive Step-by-Step Lesson**:
  - Skill: `learn`
  - Fetches math derivation, raw code, and 6-question quiz.
- **Skill & Artifact Generator**:
  - Tool: `python external/ai-engineering-from-scratch/scripts/install_skills.py`
  - Installs 414+ curated agent skills and reusable prompt artifacts.

---

## 3. Virtu Python Engine (`virtu_omni.ai_scratch`)

```python
from virtu_omni.ai_scratch import VirtuAIScratch

scratch = VirtuAIScratch()

# 1. Query curriculum and lesson concepts
lesson = scratch.get_lesson("07-transformers-deep-dive", "01-attention-mechanisms")

# 2. Run first-principles autograd engine
res = scratch.engine.verify_autograd(x=2.0, y=3.0)

# 3. Compute Multi-Head Self-Attention with KV-Cache from scratch (pure NumPy)
attn_output, kv_cache = scratch.engine.compute_attention_from_scratch(seq_len=4, d_model=64, num_heads=4)
```
