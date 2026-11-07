# Virtu Foundation Model x AI Engineering from Scratch Benchmark Report

> **Curriculum Source**: [rohitg00/ai-engineering-from-scratch](https://github.com/rohitg00/ai-engineering-from-scratch)
> **Generated**: 2026-10-29 17:54:36
> **Total Phases**: 20 | **Total Lessons**: 542 | **Quizzes**: 2087

## 1. First-Principles Mathematics Verification

| Module | Mathematical Formulation | Test Target | Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Scalar Autograd DAG** | Reverse-mode automatic differentiation with topological sort | $f=(ab+a)^2$, $a=2.0$, $b=-3.0$ | Diff < 1e-4 vs numerical | PASS |
| **Multi-Head Attention** | $\text{Softmax}\left(\frac{QK^T}{\sqrt{d_k}} + M\right)V$ + KV-Cache | `seq_len=6, d_model=64, heads=4` | Shape: `[1, 6, 64]` | PASS |
| **LoRA Low-Rank Adaptation** | $\Delta W = \frac{\alpha}{r}(B \cdot A)$, $r=8$ | `d_in=512, d_out=1024` | 97.66% trainable reduction | PASS |

## 2. 20-Phase Curriculum Breakdown

| Phase ID | Slug | Title | Lessons | Key Artifacts |
| :--- | :--- | :--- | :--- | :--- |
| `Phase 00` | `00-setup-and-tooling` | Setup And Tooling | 13 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 01` | `01-math-foundations` | Math Foundations | 22 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 02` | `02-ml-fundamentals` | Ml Fundamentals | 21 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 03` | `03-deep-learning-core` | Deep Learning Core | 13 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 04` | `04-computer-vision` | Computer Vision | 28 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 05` | `05-nlp-foundations-to-advanced` | Nlp Foundations To Advanced | 29 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 06` | `06-speech-and-audio` | Speech And Audio | 17 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 07` | `07-transformers-deep-dive` | Transformers Deep Dive | 16 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 08` | `08-generative-ai` | Generative Ai | 15 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 09` | `09-reinforcement-learning` | Reinforcement Learning | 12 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 10` | `10-llms-from-scratch` | Llms From Scratch | 24 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 11` | `11-llm-engineering` | Llm Engineering | 17 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 12` | `12-multimodal-ai` | Multimodal Ai | 25 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 13` | `13-tools-and-protocols` | Tools And Protocols | 45 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 14` | `14-agent-engineering` | Agent Engineering | 54 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 15` | `15-autonomous-systems` | Autonomous Systems | 22 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 16` | `16-multi-agent-and-swarms` | Multi Agent And Swarms | 25 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 17` | `17-infrastructure-and-production` | Infrastructure And Production | 29 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 18` | `18-ethics-safety-alignment` | Ethics Safety Alignment | 30 | `docs/en.md`, `code/`, `quiz.json` |
| `Phase 19` | `19-capstone-projects` | Capstone Projects | 85 | `docs/en.md`, `code/`, `quiz.json` |

## 3. Representative Topic Retrieval

| Query | Resolved Lesson | Rel Path | Has Code | Has Quiz |
| :--- | :--- | :--- | :--- | :--- |
| `Chain Rule And Autodiff` | `Phase 01` | `phases/01-math-foundations/05-chain-rule-and-autodiff` | True | True |
| `Attention Mechanism` | `Phase 05` | `phases/05-nlp-foundations-to-advanced/10-attention-mechanism` | True | True |
| `Controlnet Lora Conditioning` | `Phase 08` | `phases/08-generative-ai/08-controlnet-lora-conditioning` | True | False |

## 4. Placement Diagnostic Assessment

- **Assessed Score**: 5/5 (100.0%)
- **Learner Competency Level**: `Expert / Autonomous Multi-Agent Swarms`
- **Recommended Phase**: `14-agent-engineering`

## 5. REST API Integration Endpoints

| Endpoint | Method | Functionality |
| :--- | :--- | :--- |
| `/v1/ai-scratch/curriculum` | `GET` | Retrieve complete 20 phases metadata and lesson catalog |
| `/v1/ai-scratch/diagnostic` | `GET` | Retrieve 5 diagnostic questions for learner placement |
| `/v1/ai-scratch/lesson` | `POST` | Fetch specific lesson markdown, code, and quiz |
| `/v1/ai-scratch/first-principles/autograd` | `POST` | Execute analytical vs finite difference autograd verification |
| `/v1/ai-scratch/first-principles/attention` | `POST` | Compute causal Multi-Head Attention and update KV-cache |
| `/v1/ai-scratch/tutor/placement` | `POST` | Evaluate diagnostic answers and synthesize `LEARNING.md` |
