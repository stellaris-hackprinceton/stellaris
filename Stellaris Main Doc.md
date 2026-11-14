# **Stellaris**

### **From question to discovery.**

**Stellaris** is an agentic research platform that helps scientists, engineers, students, and independent researchers move from an initial question to a reproducible result.

Rather than stopping at search results or AI-generated answers, Stellaris unifies **literature discovery, deep research, experiment design, camera-based experimentation, multimedia analysis, code execution, computational research, data visualization, and scientific writing** into one intelligent, persistent workspace.

> **The idea:** Ask a research question. Find the evidence. Design and execute an experiment. Analyze what happened. Turn the outcome into something you can share—and keep everything connected.

**Project:** HackPrinceton 2026  
**Track:** Science / Discovery  
**Stage:** Hackathon MVP and long-term product vision

---

## **1\. The Problem**

Modern scientific research is fragmented across different tools and workflows.

Researchers frequently need to:

* Search academic databases to discover relevant papers.  
* Read and synthesize existing literature.  
* Organize research notes, citations, and datasets.  
* Design experimental procedures and test hypotheses.  
* Record physical experiments using cameras, microphones, and sensors.  
* Write and execute code to process experimental data.  
* Run computational experiments on local machines, cloud servers, or supercomputers.  
* Analyze images, videos, audio, numerical data, and experimental observations.  
* Generate charts, visualizations, reports, and scientific documents.  
* Maintain project context across long research cycles.

These activities are often performed in disconnected applications, forcing researchers to constantly transfer information between environments.

Although AI research assistants can summarize papers and answer questions, they rarely support the **entire research lifecycle**, especially the transition from theoretical research to real experimental execution.

Stellaris aims to eliminate this fragmentation.

## **2\. The Vision**

**Stellaris is an intelligent research operating system capable of orchestrating the complete scientific discovery process.**

Researchers interact with an AI-powered workspace that understands their goals, investigates relevant knowledge, plans experiments, executes computational or multimedia workflows, analyzes observations, and generates scientific deliverables.

The platform combines research intelligence with real execution capabilities.

### **Research lifecycle**

1. **Discover:** Search scientific literature, technical sources, and project knowledge.  
2. **Understand:** Synthesize findings, compare methods, and identify gaps in existing research.  
3. **Hypothesize:** Develop testable scientific hypotheses and investigation strategies.  
4. **Design:** Construct experimental procedures, identify variables, and select measurement tools.  
5. **Experiment:** Execute computational experiments or collect real-world observations using cameras, microphones, uploaded media, and connected devices.  
6. **Analyze:** Process experimental data, extract measurements, and generate visualizations.  
7. **Document:** Produce scientific reports, summaries, technical documents, and reproducible artifacts.  
8. **Iterate:** Refine experiments and continue investigating using persistent project context.

**Core principle:** Stellaris is not simply a chatbot for science. It is an environment where scientific research happens.

---

## **3\. Core Capabilities**

### **3.1 Agentic Deep Research**

Stellaris provides autonomous, multi-step research functionality.

**Capabilities:**

* Natural-language research questions.  
* Academic paper discovery through sources such as arXiv, OpenAlex, and Semantic Scholar.  
* Web search and technical documentation retrieval.  
* Paper metadata extraction and source management.  
* Literature reviews and evidence-backed summaries.  
* Comparison of competing scientific approaches.  
* Identification of unanswered questions and research gaps.  
* Contextual research using existing project documents.  
* Source-grounded citations and bibliographies.

**Example:**

A user asks:

"Investigate existing methods for estimating motion and energy loss from video recordings."

Stellaris searches relevant literature, compares available methods, identifies suitable approaches, and builds an evidence-backed research brief.

### **3.2 Intelligent Experiment Design**

Stellaris transforms research questions into executable experiments.

The agent can:

* Formulate hypotheses.  
* Identify independent, dependent, and controlled variables.  
* Propose experimental methodologies.  
* Define measurement procedures.  
* Suggest equipment, data sources, and computational resources.  
* Generate experimental protocols.  
* Establish success metrics and evaluation criteria.  
* Design repeated trials and comparative experiments.  
* Identify potential sources of error and uncertainty.

Experiments may be entirely computational, entirely physical, or combine both.

### **3.3 Camera-Based Experimentation**

**Camera-based experimentation is a first-class Stellaris capability.**

Researchers can connect a webcam, use a compatible mobile camera, or upload existing recordings to conduct physical experiments.

**Capabilities:**

* Live camera preview and user-controlled recording.  
* Capture of images and video from physical experiments.  
* Timestamped frame acquisition.  
* Motion and object tracking.  
* Object detection and classification.  
* Measurement of positions, displacement, and trajectories.  
* Estimation of velocity and acceleration.  
* Frame-by-frame analysis.  
* Visual comparison between experimental conditions.  
* Annotated video and image generation.  
* AI-assisted interpretation of visual observations.  
* Preservation of raw recordings and derived measurements.

**Example experiments:**

**Bouncing ball experiment**

* Record a ball bouncing using a webcam.  
* Identify and track the ball across frames.  
* Estimate successive bounce heights.  
* Calculate energy retention under appropriate physical assumptions.  
* Visualize the decay in bounce height.  
* Produce a scientific report.

**Pendulum experiment**

* Record a moving pendulum.  
* Track the pendulum's position over time.  
* Estimate its oscillation period.  
* Compare results with theoretical predictions.

**Plant growth experiment**

* Import images captured over multiple days.  
* Track visible growth or changes in appearance.  
* Generate measurements and time-series plots.  
* Compare different experimental conditions.

**Important:** Measurements should include calibration assumptions and uncertainty where appropriate. A camera recording alone does not always provide a reliable physical scale.

### **3.4 Multimedia-Based Experimentation**

Stellaris supports experimentation using multiple data modalities, rather than limiting experiments to numerical datasets and computational jobs.

**Supported modalities:**

* Images  
* Video  
* Audio  
* Microphone recordings  
* Time-series data  
* CSV and JSON datasets  
* Experimental logs  
* Combinations of synchronized media and measurements

**Computer vision capabilities:**

* Frame extraction  
* Object tracking  
* Image segmentation  
* Visual feature extraction  
* Motion analysis  
* Image comparison  
* Color and intensity measurements  
* Temporal event detection

**Audio and signal-analysis capabilities:**

* Waveform analysis  
* Frequency-domain analysis  
* Spectrogram generation  
* Event detection  
* Sound comparison  
* Resonance analysis  
* Temporal signal measurements

**Multimodal workflows:**

Stellaris can combine visual observations, sound recordings, numerical measurements, and external reference material within the same experiment.

For example, a researcher could upload a video of a mechanical system alongside an audio recording and a CSV file containing sensor measurements.

Stellaris can analyze the individual sources, align observations where timestamps permit, and investigate relationships between events.

**All analysis must distinguish directly observed data from inferred or AI-generated interpretations.**

### **3.5 Computational Experimentation**

Stellaris can generate, execute, and analyze scientific code.

**Capabilities:**

* AI-assisted code generation.  
* Python-based scientific computing.  
* Data transformation and processing.  
* Algorithmic experiments.  
* Numerical simulations.  
* Statistical analysis.  
* Parameter sweeps.  
* Automated plotting.  
* Error diagnosis and code iteration.  
* Run logs and execution histories.  
* Reproducible experiment artifacts.

Potential libraries include NumPy, SciPy, pandas, matplotlib, OpenCV, and other task-specific scientific packages.

Execution should take place in controlled environments with appropriate resource, filesystem, time, and network restrictions.

### **3.6 Remote Computing and HPC**

Remote computing and high-performance computing are optional execution backends within Stellaris.

They are not required for its core scientific experimentation functionality.

**Possible capabilities:**

* Execution on local machines.  
* Container-based experiment workers.  
* Cloud computation.  
* Remote server access.  
* HPC cluster connectivity.  
* Slurm job submission.  
* Job monitoring and log streaming.  
* Collection and analysis of generated artifacts.

For example, a researcher could develop an experiment using local data, then dispatch a computationally intensive simulation to a connected research cluster.

The same workspace would manage the research question, experimental procedure, execution status, and results.

Expensive or privileged execution should require explicit authorization.

### **3.7 Scientific Data Analysis**

Stellaris transforms experimental outputs into interpretable scientific findings.

**Capabilities:**

* Reading and processing scientific datasets.  
* Statistical summaries.  
* Data visualization.  
* Comparison between experimental runs.  
* Trend identification.  
* Hypothesis evaluation.  
* Model fitting where appropriate.  
* Error and uncertainty estimation.  
* Automated generation of charts and tables.  
* Export of plots, measurements, and analytical results.

Researchers can inspect both the original observations and derived results.

### **3.8 Scientific Writing and Documentation**

Stellaris generates research deliverables grounded in actual sources and experiment results.

**Document types:**

* Research briefs  
* Literature reviews  
* Experiment reports  
* Scientific summaries  
* Technical documentation  
* Research proposals  
* Methodology descriptions  
* Reproducibility reports  
* Project documentation

Reports can incorporate citations, hypotheses, experimental methods, recorded measurements, charts, analysis, limitations, and future research directions.

Markdown is the initial export format. PDF and DOCX can be supported as additional export formats.

### **3.9 Persistent Research Workspace**

Each Stellaris project provides a persistent environment for the complete research lifecycle.

A project contains:

* Research questions  
* Chat and agent history  
* Scientific papers and references  
* Uploaded documents  
* Source datasets  
* Camera recordings and multimedia files  
* Experimental plans  
* Code and notebooks  
* Execution logs  
* Experimental results  
* Measurements and annotations  
* Charts and visualizations  
* Reports and generated artifacts  
* Research conclusions and follow-up tasks

The workspace is the source of truth, while chat serves as the primary interface for directing the research process.

---

## **4\. Product Experience**

Stellaris uses a unified research interface composed of five connected areas.

| Component | Purpose |
| ----- | ----- |
| **Research Chat** | Communicate with the agent, specify goals, and direct research workflows. |
| **Research Canvas** | Explore literature, scientific findings, hypotheses, and research plans. |
| **Experiment Studio** | Record experiments, upload multimedia, configure analyses, and inspect evidence. |
| **Execution Panel** | View running code, experiment progress, logs, outputs, and visualizations. |
| **Project Workspace** | Organize papers, datasets, media, code, experiments, reports, and project files. |

The interface should allow researchers to navigate naturally between scientific evidence, experiment execution, and final findings.

### **Experiment Studio**

The Experiment Studio is a defining component of Stellaris.

It provides:

* Camera preview with visible recording controls.  
* Image, video, and audio uploads.  
* Experiment setup and configuration.  
* Measurement and calibration options.  
* Live experiment status.  
* Multimedia preview and annotation.  
* Generated measurements and graphs.  
* Results comparison.  
* Access to raw and processed artifacts.

The goal is to make real-world experiments as accessible as computational ones.

---

## **5\. Technical Architecture**

Stellaris follows an orchestrator-and-tools architecture.

A primary AI agent understands the user's research goals, develops a plan, delegates specialized tasks, and coordinates available tools.

### **Architecture overview**

```
              STELLARIS FRONTEND
       ┌──────────────────────────────┐
       │ Research Chat                │
       │ Research Canvas              │
       │ Experiment Studio            │
       │ Execution Panel              │
       │ Files and Project Workspace  │
       └──────────────┬───────────────┘
                      │
                API / Events
                      │
       ┌──────────────▼───────────────┐
       │        BACKEND API           │
       │ Projects, Files, Runs, Auth  │
       └──────────────┬───────────────┘
                      │
       ┌──────────────▼───────────────┐
       │       AI ORCHESTRATOR        │
       │ Planning / Tool Routing      │
       │ Agent State / Delegation     │
       └──────────────┬───────────────┘
                      │
       ┌──────────────▼───────────────┐
       │       SPECIALIZED TOOLS      │
       │                              │
       │ Literature Search            │
       │ Deep Research                │
       │ Experiment Planning          │
       │ Camera / Multimedia Analysis │
       │ Code Execution               │
       │ Scientific Data Analysis     │
       │ Remote Compute / HPC         │
       │ Report Generation            │
       └──────────────┬───────────────┘
                      │
       ┌──────────────▼───────────────┐
       │     PROJECT PERSISTENCE      │
       │ Files / Research / Media     │
       │ Code / Runs / Results        │
       │ Reports / Citations          │
       └──────────────────────────────┘
```

### **High Level Design**

![][image1]

### **Proposed Technology Stack**

| Layer | Technology |
| ----- | ----- |
| Frontend | React / Next.js |
| Backend | Python / Flask |
| Agent orchestration | LangChain Deep Agents / LangGraph |
| LLM | Configurable model provider |
| Literature search | arXiv, OpenAlex, Semantic Scholar |
| Camera and microphone access | Browser Media APIs |
| Image and video analysis | OpenCV, Python |
| Audio and signal processing | NumPy, SciPy |
| Scientific computing | Python, pandas, matplotlib |
| Execution | Isolated Python workers / Docker  |
| Project database | SQLite |
| Artifact storage | Local filesystem initially → Project has own docker container where project data is stored |
| Real-time communication | SSE / WebSockets |
| Optional HPC integration | SSH / Slurm |

LangChain Deep Agents is a candidate for orchestrating complex research workflows, but the architecture should remain modular and independent of any single framework.

---

## **6\. Agent Architecture**

Stellaris can evolve into a coordinated multi-agent research system.

### **Research Orchestrator**

The primary agent responsible for:

* Understanding research goals.  
* Breaking complex tasks into smaller activities.  
* Selecting tools and delegating work.  
* Tracking experiment and research progress.  
* Managing intermediate results.  
* Coordinating final deliverables.

### **Literature Research Agent**

Responsible for:

* Scientific paper discovery.  
* Source retrieval.  
* Research synthesis.  
* Citation management.  
* Identifying knowledge gaps.

### **Experiment Agent**

Responsible for:

* Developing hypotheses.  
* Designing experiments.  
* Establishing measurement methods.  
* Generating analysis code.  
* Executing and iterating experiments.  
* Managing experimental outputs.

### **Multimedia Analysis Tools**

Responsible for:

* Processing camera recordings.  
* Extracting video frames.  
* Analyzing images and audio.  
* Object and motion tracking.  
* Extracting quantitative measurements.  
* Generating annotated evidence.

### **Data Analysis Agent**

Responsible for:

* Statistical analysis.  
* Visualization.  
* Comparing results.  
* Identifying trends.  
* Evaluating hypotheses.  
* Explaining limitations.

### **Writing Agent**

Responsible for:

* Research summaries.  
* Experimental reports.  
* Literature reviews.  
* Scientific documentation.  
* Final research deliverables.

For the first implementation, these roles can begin as a single orchestrating agent with specialized tools. Dedicated subagents can be introduced when useful.

---

## **7\. End-to-End Research Workflow**

### **Example: Investigating Energy Loss in a Bouncing Ball**

**User prompt:**

"Investigate how much energy a ball loses every time it bounces. Find the relevant physics, use my camera to record an experiment, analyze the motion, and generate a scientific report."

**Step 1 — Research**

Stellaris searches for relevant physics methods and explains how bounce height relates to mechanical energy under an appropriate physical model.

**Step 2 — Hypothesis**

The agent proposes a hypothesis and defines variables, experimental conditions, and measurement assumptions.

**Step 3 — Experiment Design**

Stellaris produces an experimental protocol, identifies camera positioning requirements, and explains how the measurements will be obtained.

**Step 4 — Data Collection**

The researcher grants camera access and records the experiment, or uploads an existing video.

**Step 5 — Processing**

Stellaris runs a video-analysis pipeline to detect and track the ball across frames.

**Step 6 — Measurement**

The system estimates bounce heights and extracts relevant observations.

**Step 7 — Analysis**

Stellaris calculates energy-retention estimates under stated assumptions, creates plots, and discusses experimental uncertainties.

**Step 8 — Documentation**

A scientific report is generated using the recorded evidence, measurements, methodology, citations, charts, and limitations.

**Step 9 — Persistence**

The recording, code, experiment run, data, graphs, and report remain available in the project workspace.

This workflow demonstrates a complete scientific investigation rather than a standalone AI response.

---

## **8\. Experiment Provenance and Trust**

Scientific accuracy and transparency are central to Stellaris.

Every experiment should retain sufficient information to explain how a result was produced.

### **Requirements**

* Preserve original experimental inputs.  
* Track source documents and citations.  
* Store generated code and relevant processing parameters.  
* Retain execution logs and outputs.  
* Link measurements to their originating media or dataset.  
* Record calibration assumptions where applicable.  
* Distinguish observations from inferences.  
* Report uncertainty and limitations.  
* Show failed experiments and processing errors accurately.  
* Obtain permission before recording camera or microphone data.  
* Require approval before expensive, destructive, or privileged execution.

**Stellaris must never present a proposed experiment as completed, or simulated data as though it were a real observation.**

---

## **9\. HackPrinceton MVP**

The HackPrinceton goal is to demonstrate a complete research-to-experiment-to-result workflow.

### **Core MVP Features**

* Create and manage a research project.  
* Interact with an intelligent research agent.  
* Search scientific papers and retrieve supporting sources.  
* Generate literature summaries with citations.  
* Design experiments from research questions.  
* Capture webcam footage or upload an experimental video.  
* Execute a reproducible multimedia-analysis pipeline.  
* Generate measurements from experimental evidence.  
* Display annotated frames or video.  
* Visualize experimental results.  
* Execute analysis code in a controlled environment.  
* Generate a scientific Markdown report.  
* Preserve files, sources, code, results, and reports in the workspace.

### **Stretch Goals**

* Both webcam recording and video upload.  
* Microphone recording and audio experimentation.  
* Multimodal video-and-audio analysis.  
* Multiple specialized agents.  
* Remote execution and HPC connectivity.  
* Experiment comparisons.  
* Advanced scientific visualization.  
* PDF / DOCX document generation.  
* Citation and knowledge graphs.  
* Collaborative research workspaces.

### **MVP Priority**

**Complete one end-to-end workflow before expanding into more modalities or integrations.**

A working camera/video experiment with actual measurements and a generated report demonstrates more value than several disconnected features.

---

## **11\. Hackathon Demo**

### **Opening**

"Today's AI can tell you how to do research. Stellaris helps you actually do it."

### **Demo Sequence**

**1\. Scientific question**

Ask Stellaris to investigate the energy loss of a bouncing ball.

**2\. Literature discovery**

Demonstrate academic search, source retrieval, and a cited explanation of the relevant scientific principles.

**3\. Experiment design**

Show an automatically generated experimental protocol and the measurements required to test the hypothesis.

**4\. Multimedia input**

Capture the experiment through a webcam or upload a recorded video.

**5\. Experiment execution**

Run the analysis and show processing progress, logs, and annotated frames.

**6\. Data analysis**

Display extracted bounce heights, charts, and estimated energy retention.

**7\. Scientific report**

Generate a report with source references, experimental methods, measured results, plots, and limitations.

**8\. Research workspace**

Show all associated papers, recordings, analysis code, datasets, charts, and reports connected to the same project.

For demo reliability, keep a previously completed experiment available as a clearly labeled fallback if camera access, lighting, or external services fail.

---

## **12\. Competitive Differentiation**

| Traditional Research Workflow | Stellaris |
| ----- | ----- |
| Search papers in separate applications | Integrated academic research and citations |
| Maintain disconnected research notes | Persistent, contextual research workspace |
| Record experiments outside the research environment | Integrated camera and multimedia experimentation |
| Manually analyze experimental recordings | AI-assisted feature extraction and measurement pipelines |
| Move analysis code between tools | Integrated code generation and execution |
| Store experimental outputs separately | Linked experiments, recordings, measurements, and artifacts |
| Manually prepare scientific reports | Evidence-grounded scientific report generation |
| Reconstruct context across sessions | Persistent research state and project history |

The core differentiation is **end-to-end scientific orchestration with real, inspectable experimental evidence**.

---

## **13\. Success Criteria**

For HackPrinceton, Stellaris succeeds when it demonstrates that:

1. A scientific question can become an actionable research workflow.  
2. Research conclusions reference identifiable evidence.  
3. The platform can process real experimental data from a camera, video, image, audio recording, or computational job.  
4. The resulting measurements are inspectable.  
5. The system generates meaningful scientific analysis and visualizations.  
6. Reports accurately incorporate the research and experimental results.  
7. All supporting materials remain accessible in one project.

The objective is to make scientific research more accessible, connected, and reproducible.

---

## **14\. Long-Term Vision**

Stellaris could develop into a general-purpose research environment capable of coordinating scientific investigations across physical and digital systems.

Future capabilities may include:

* Connected scientific instruments and sensors.  
* Laboratory robotics and automated experiment control.  
* Live multimodal observation.  
* Multi-device data collection.  
* Collaborative research environments.  
* Long-running autonomous research workflows.  
* Cloud and supercomputing integrations.  
* Reproducible scientific pipelines.  
* Structured scientific knowledge bases.  
* Automated experiment optimization.  
* Cross-disciplinary research collaboration.

The long-term goal is not simply to make research faster. It is to enable researchers to move seamlessly between **curiosity, evidence, experimentation, computation, and discovery**.

---

# **Stellaris — Research Beyond the Answer.**

*An intelligent workspace for scientific discovery.*

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAnAAAAH9CAYAAACa1UE4AACAAElEQVR4Xuy9ia8e1ZH+//0bZp8M2GOwTRwP3sY2EIgGRoDBGUAERzAYgTwIYkEwIJYBImAMYUjE5gDix+KwGMPExqwJJgQDATKBsAlCsCBhcQgimMUglohlyPvLc5J6029111t96t7b9759n5I+ureru7pPn+7q87x9uk//v3/913/t/MVf/EU2//AP/9D5y7/8y5LfA3Ha5/FXf/VXKe7v//7vS/M8sH/bb799ye/xd3/3d52//uu/Lvk9Pve5z4X2EUTitt5667SP2u/xN3/zN6HtAcRF6yZyzmD//uVf/qXk98B5EzlnUDd/+7d/W/J74JyJ1in2MXebqMvo9qL5hLjccoJ//ud/7vzjP/5jye8Rzado3eC8jsQBHMMvfOELJb9H0/mE7SFW+z1w/HActd8D50ukTnF+RusGcbl1g3JGrqUA20P+a78HtonrjfZ7SN1ovweuo5F9RF1Gzpmh5BPiInUzf/781C5qv8dQyhmtm8g580//9E/dY/j/8A8hhBBCCBkckoDbdttts5k2bVpn8uTJJX8/sDzitN9jypQpKe7zn/98aZ4H9m/u3Lklv8d2223XmTp1asnvgTJG9jFaN9OnT0/7qP0e2LfI9gDicEy03yNyzgDs36677lrye6CMkXMGdYPjr/0eiInWKfYxd5vRcwZE8wlxkbzYcccd051w7ffA9iL7GK0budZofx1wDHGHSvs9ms6naJ3i+OE4ar9H9Foj19Km6gb5F7mWAmwvN39B0+0MrqORfRyNfIpea774xS+mdlH7PSLnjMRFrqXRdgZ6Ro5hEnD6Fl0dIreoJU77PNiFasMuVBt2odpE8wlxueUE7EK1aTqfol0+7EK1wfYi3WHsQrVBXKRuxl0Xql6gDpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBZ4PtRRpjCjgbxEXqhgKuBpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBZ4PtRRpjCjgbxEXqhgKuBpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBZ4PtRRpjCjgbxEXqhgKuBpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBZ4PtRRpjCjgbxEXqhgKuBpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBZ4PtRRpjCjgbxEXqhgKuBpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBZ4PtRRpjCjgbxEXqhgKuBpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBZ4PtRRpjCjgbxEXqhgKuBpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBZ4PtRRpjCjgbxEXqhgKuBpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBZ4PtRRpjCjgbxEXqhgKuBpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBZ4PtRRpjCjgbxEXqhgKuBpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBZ4PtRRpjCjgbxEXqZtwJOGw8Fyl0LkOJi8Ri/2bNmlXye0S2JXFDidU+D3zQdpCOofbVQQSc9tchss3oMYzGAezjhAkTSn6P6PaiZY3GzZs3L328Wfs9otuTWO2rQzQOx3DGjBklv0d0e0OJi8Ti+OE4ar9HdHvROInVPg/k31CupZFtNh0nAk776xDZ3mjE7bjjjqld1H6P6Paix0Jitc8DekaOYRJwUNe5YMNQkNrfD7mTpv0eouJRYD3PA/uHO3Da74FfOFD/2u8hB0X7PaJ1M3HixLSP2u8hv4q1vw6Ii9ZN7jkDRMBpvwfKiOOo/R6oG/wy0n4P+VWs/XXAPuaWNXrOAMTlbk/iInWDOzeTJk0q+T3k4qj9HtG6kTvT2l8HHEPcgdN+j2g+IQ77qf0e0Wspjh+Oo/Z7RK81kk9N1Q22F7mWgmg+IZdQP9rvEb3WiIDTfg9ctyPnzFDyCXGRusEdOLSL2u8ROWckLlo3kXMGekaOIbtQDdiFaoO4aN1EzhkRcNrvwS5Um2g+yUVV+z3YhWrTdD5Jg6P9HuxCtcH2It1h7EK1QVykbsZdF6peoA6RBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDAWeD7UUaYwo4G8RF6oYCrgaRBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDAWeD7UUaYwo4G8RF6oYCrgaRBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDAWeD7UUaYwo4G8RF6oYCrgaRBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDAWeD7UUaYwo4G8RF6oYCrgaRBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDAWeD7UUaYwo4G8RF6oYCrgaRBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDAWeD7UUaYwo4G8RF6oYCrgaRBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDAWeD7UUaYwo4G8RF6oYCrgaRBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDAWeD7UUaYwo4G8RF6oYCrgaRBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDAWeD7UUaYwo4G8RF6oYCrgaRBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDAWeD7UUaYwo4G8RF6oYCrgaRBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDAWeD7UUaYwo4G8RF6mbcCTgUoK1g/2bPnl3yt4UpU6akfdT+NiECTvvbBPYRDaT2twVcVLfbbruSv03gGM6YMaPkbws4fjiO2t8WkH9tv5aKgNP+NrHjjjumdlH72wL0jBxDCrgBZ/Lkya1PSAq4wYcCbvAZLwIO7QV6bdrIvvvu29l///1L/jax1157debNm5f+18e4DZQEnL5FVwcE596iljjt82AXqg27UG3YhWoTzSfE5ZYTsAvVpul8wvYiXT7jpQt1zfe+16G1w/Qx7kfkHJW4SD4NWxeqXqAOkQSROO3zoICzoYCzoYCzieYT4nLLCSjgbJrOp2iDM94EnJ5PBoevfvWr2ccwco5KXCSfKOBqQAFXDQWcDQWcDeJyywko4Gyazqdog0MBRwYFCjiHSIJInPZ5UMDZUMDZUMDZRPMJcbnlBBRwNk3nU7TBoYAjgwIFnEMkQSRO+zwo4Gwo4Gwo4Gyi+YS43HICCjibpvMp2uBQwJFBgQLOIZIgEqd9HhRwNhRwNhRwNtF8QlxuOQEFnE3T+RRtcCjgyKBAAecQSRCJ0z4PCjgbCjgbCjibaD4hLrecgALOpul8ijY4FHBkUKCAc4gkiMRpnwcFnA0FnA0FnE00nxCXW05AAWfTdD5FGxwKODIoUMA5RBJE4rTPgwLOhgLOhgLOJppPiMstJ6CAs2k6n6INDgUcGRQo4BwiCSJx2udBAWdDAWdDAWcTzSfE5ZYTUMDZNJ1P0QaHAo4MChRwDpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBRwYFCjiHSIJInPZ5UMDZUMDZUMDZRPMJcbnlBBRwNk3nU7TBoYAjg8K4EnAoQFvB/rX5Y/ZTpkxJ+6j9bUIEnPa3CewjGkjtbwv8mP3gM14+Zr9u3brsxp+MLUTA6WPcBkofs8cvnVwQDNWp/R6I0z4P+RUeicX+zZo1q+T3GMr+Rcopsdrnse2226Z91H4PqVPtr8NQ6kb76iACTvs9ovuIuOj+RbYHsI8TJkwo+T2i24uWNXrs582bl35saL9HtJwSq30e0XMG4Bjibr/2e0TrNFrOaJ3i+OE4ar9HtE6lnE3VDfIPx/Cmm26igBtwRMDpY9yPyDkjcZHYaF5Az0ibzy5UA3ah2iAuWjeRc0YEnPZ7sAvVJppPiMstJ2AXqk3T+YTtIVb7PdiFSgaFcdWFqheoQyRBJE77PCjgbCjgbCjgbKL5hLjccgIKOJum8yna4FDAkUGBAs4hkiASp30eFHA2FHA2FHA20XxCXG45AQWcTdP5FG1wKODIoEAB5xBJEInTPg8KOBsKOBsKOJtoPiEut5yAAs6m6XyKNjgUcGRQoIBziCSIxGmfBwWcDQWcDQWcTTSfEJdbTkABZ9N0PkUbHAo4MihQwDlEEkTitM+DAs6GAs6GAs4mmk+Iyy0noICzaTqfog0OBdzw8c4776RtVNm1114b2ucqxLS/aXbeeefOpk2bSv6RggLOIZIgEqd9HhRwNhRwNhRwNtF8QlxuOQEFnE3T+RRtcCjgho9+Ag720ksvlWIiiGn/UMA5ALv66qtL8yxuueWWYS9HPyjgHCIJInHa50EBZ0MBZ0MBZxPNJ8TllhNQwNk0nU/RBocCbvgQAaf9QEz7xwo77LBDKt/1119fmqd54IEHOm+++Wbj+0QB5xBJEInTPg8KOBsKOBsKOJtoPiEut5yAAs6m6XyKNjgUcMNHjoC74IILOmeeeWZn4cKFnXvvvTcJKJm3ePHizto1azovvvhi55577imt67TTTkto/6pVqzqPP/54irHycvXq1Z2NGzd2Hn300c63v/3tnljYs88+m8q27777lmIFbXr+SEEB5xBJEInTPg8KOBsKOBsKOJtoPiEut5yAAs6m6XyKNjgUcMNHjoCD/f73v+/699lnn+T/5S9/maY//fTTJLQ+/vjjNP3xRx+Z6/roD/PSMn9YFt207733XmkZEWiwLVu2pPXBcCetWHb44VuxYkVpHzQQmMVtjDQUcA6RBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naINDATd8VAm4Aw44oLNmzZrkL84Te/rppzt777138i1ZsiT5sJ6pU6cmH653YjpWTxdzWMShXA8+++yzNA0RhGnU5RtvvJF8EI85XagCBVwZCrgaUMBVQwFnQwFng7jccgIKOJum8yna4FDADR/9XmJ44YUXOtOmTesuK1aMx1037QMilKZPn16KXbp0afr/sssu64nBG6IwdJXqmCLnnXde6i6lgCvHRfJp2AQcFHwuWMl2221X8nsgTvs8Pv/5z6c4nJR6ngf2b/78+SW/By7E2K72e6CMkX1EXUbiIE4jxxAXiMj2AOKidRM5Z7B/u+66a8nvgTLiOGq/B+oGaL8HthWtU2n8tb8f0XMGIC53exIXqZuddtqpM3PmzJLfYyj5FLleyLVG++uAYzh37tyS36PpfIpeS3H8cBy13yN6rZF8itQN4nLrBtvDMbztttuyG/9cRMDhjpuAZ85OPfXU0rJiMr3NNtuUfMKtt96a/Icffngp9oorrkj/Q/yhC7UIDCJLYnBXTq9bGCQBp49xPyLnjMRF8inaPkHPSJufBBxEQC6zZ88u+eoQiZsxY0aKmzVrVmmeB/YPFx3t98DFCtvVfg+UMbKPIBI3Z86c7l3GHGb+qU61vw6Ii9aN9tUB+7fbbruV/B4oY2SbOPZA+z0QE61T7GNkm9HtRfMJcZFy4lc+7t5ov8dQ8imyf3Kt0f464BiicdN+j6bzKXrscfxwHLXfI5oXcuwjdRPZHsqJY/j9739/xMVGVReqhZhMQzBon3DHHXckP9o8HXvNNdek/y+55JLOokWLShRjPvzww9K6hUEScPoY9yNyzkhcJJ9wXkeupTvuuGO3zWcXqgG7UG2i3RrRLh/sH7tQy0S7CUE0nxCXW07ALlSbpvMp2uXDLtThYygCDshza3rZzZs3Jz+ufTr2uOOOS/9feeWVPTGoZ/gg4iRG34GDcMezcbhLOEgCTvv7ETlHJS6ST8PWhaoXqEMkQSRO+zwo4Gwo4Gwo4Gyi+YS43HICCjibpvMp2uBQwA0fQxVwRx11VPLhrVK5/uMOml7Wmi7mvvUSwymnnJKmMQwJDF2vOBboZoS9+uqrqf3R5a2CAq4MBVwNKOCqoYCzoYCzQVxuOQEFnE3T+RRtcCjgho+hCjjw/PPPd+fJ8CAwjO9mxcqQIDB0k4pYKy5z/vnnd33F4UuWLVvWXeb999/v+tevX18qm4YCrgwFXA0o4KqhgLOhgLNBXG45AQWcTdP5FG1wKODGHnh4Hl2j6AI95JBDSvPFtH/58uWdm266qXPppZeW5gkLFixIA/jizdOqY3DQQQd19ttvv9CxHWko4BwiCSJx2udBAWdDAWdDAWcTzSfE5ZYTUMDZNJ1P0QaHAm7wsARc26GAc4gkiMRpnwcFnA0FnA0FnE00nxCXW05AAWfTdD5FGxwKuMHh4osv7oo3DBOi57cdCjiHSIJInPZ5UMDZUMDZUMDZRPMJcbnlBBRwNk3nU7TBoYAbHETA4Rm2k046qTS/7VDAOUQSROK0z4MCzoYCzoYCziaaT4jLLSeggLNpOp+iDQ4F3OCAscmOP/74UK62AQo4h0iCSJz2eVDA2VDA2VDA2UTzCXG55QQUcDZN51O0waGAI4MCBZxDJEEkTvs8KOBsKOBsKOBsovmEuNxyAgo4m6bzKdrgUMCRQYECziGSIBKnfR4UcDYUcDYUcDbRfEJcbjkBBZxN0/kUbXAo4MigQAHnEEkQidM+Dwo4Gwo4Gwo4m2g+IS63nIACzqbpfIo2OBRw9cG15+abb+7xYTw1jL0mn6xavHhx99o9ceLENI0P1et1kXzGlYDDSnKRBkD7PRCnfR6SyJFY7B8+GKv9Hjgg0f2LlFNitc8DCR85hlKn2l+HJo89EAGn/R4oI46j9nsgJho3lH2EGNd+j+j25KKj/R7RuHnz5nWmTJlS8ns0nU9DyQv5saj9Hk3nU7ROcfxwHLXfI5oXEtdU3ciPYYis3MZfI184kGn5ogE+R3XRRRclHwzfLsX/Rx55ZJo+4YQTSusabcS0fywjAk4f435EzhmJi8RG2yfoGWnzk4CTArQR7B/eyNH+toCL6ng4hhBw2t8msI+4w6H9bWH+/PnpG4ra3yZwDGfMmFHytwUcPxxH7W8LyD8cw3Xr1g1ZsMBef/31nmm9zqeeeqqzatWq9D8F3PAiAk4f4zYAPSNtPrtQDaBuI7fuo10+IBLHLlQbdqHaRPMJcbnlBOxCtWk6n7C9SJcPu1Dr8fTTT6fBc3H9QdlPPfXUrgjCh+F33nnntBz+R7cp/rcE3GGHHZa+bXrPPfeY+YP141uj2G7xc1r4/4ILLkhdbsXl8fkt+CFyMI26uvzyyzubNm3qPPLII51dd921u+w3vvGNbtkRg25gmbfHHnt0Lrnkks7DDz/cOeecc5KwKG4HXcVnnXVW+h+f5EL5ZN34MXD22WenfcM6dtppp57YoTKuulD1AnWIJIjEaZ8HBZwNBZwNBZxNNJ8Ql1tOQAFn03Q+RRscCjgflBndpRs2bEjTU6dO7QogsdWrV6d5sH5dqC+99FIxLK33xBNP7Nne22+/3bMM7P7770/z1q5dm6Zle8L111+f/Ph+KqYhNouG7XzrW9+qnHf33XcnP66tVVbczk9+8pO0Lgi0okG06fWiy7kYO1Qo4BwiCSJx2udBAWdDAWdDAWcTzSfE5ZYTUMDZNJ1P0QaHAs7ngQceSLEQbkW/mPZZAu7OO+9M0w8++GB3eXmOTvJ28uTJaRpCT5b58MMPk8/aLo5fMQZ3AWHSlVsVo6eXLl2aplF2ubs3a9as7rblJQ0IOBjKrdeFu314/Af78vLLLyffcL7AQQHnEEkQidM+Dwo4Gwo4Gwo4m2g+IS63nIACzqbpfIo2OBRwPq+88kplrJj2VQk4dC9C9Lz11ls9y69cuTIts3z58jSNLlKY3BUDuHP22muvdXNUTOZDqBXXgTdlYcccc0x3GXTXYh3FchbXsWXLljSN5z2L5VuwYEHyoxsW0yLgbr311tK60I0rPnS/wo444oie9Q0FCjiHSIJInPZ5UMDZUMDZUMDZRPMJcbnlBBRwNk3nU7TBoYDz+fijjypjxbSvSsBdccUV6X+8sYquxiIwPO+m1wuD6Lvmmmt6hNULL7yQ5uEOWVU50H4UDduECCxeG8T0tC6blE+6Q0XAFY/9J5980rMucNxxxyXfN7/5zR7/UKCAc4gkiMRpnwcFnA0FnA0FnE00nxCXW05AAWfTdD5FGxwKOB89fIggpn1VAg53wPoZ7vLJOlasWNF5//339SLd+dJFirt3VjnuWr++9EwahJxVds+ky1SegStuiwLuz1DA1YACrhoKOBsKOBvE5ZYTUMDZNJ1P0QaHAs7n3XffrYwV074qASeCRl4yEFAf8MkzZnhD9bzzzutZ5sknn0yxV111Vdf32GOPJd/ChQvT3/vuu687D12pRx99dM86RBDiLVMpJ0zm6+ki2O7JJ5+c/s8VcOhK1euLQgHnEEkQidM+Dwo4Gwo4Gwo4m2g+IS63nIACzqbpfIo2OBRwPo8++mhlrJj2VQm4OXPmpP8hpIrL33DDDcl/5plnpuk77rgjTReH4Nhtt92SD2+aig9CD/bOO++kv3vvvXd3HraPbt/idjCkCGy//fbrlhMm8+VlBT1siIgmDCuCaQq4/lDA1YACrhoKOBsKOBvE5ZYTUMDZNJ1P0QaHAs4Hz5/B8Cxa0S+mfVUCDtPyhikMgkm6ZmF6HTC8WPDee+9VLlNc7rvf/W6PHy8TiL3xxhvdZ/hgskyxi3b9+vXJJ8/WwT4qxNxyyy3duKiAO/fcc9P0E0880bNcDhRwDpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4Gyazqdog0MBVw8InuKLBkBM++RrDYcffniaXrZsWXf+888/342D4dm34kC6QI8VB3vmmWdKZRLD0B163gcffFCI/uMzbMU3Ry+99NLuvH7jwEFoFteLIVDqCDh04cJk0F88CwfDeHHF5XKggHOIJIjEaZ8HBZwNBZwNBZxNNJ8Ql1tOQAFn03Q+RRscCrh6YNswfFNVzxstxLR/rII7hQcddFDJXxcKOIdIgkic9nlQwNlQwNlQwNlE8wlxueUEFHA2TedTtMGhgKsPrPgm52iBusMQIjB8tUHPH4ucdNJJqbyR4y5QwDlEEkTitM+DAs6GAs6GAs4mmk+Iyy0noICzaTqfog0OBVx9fvvb3w55HcOBfL0BBmGk549F8NKFfIosyrgScChAW8H+4W0Z7W8LeKZhPBxDCDjtbxPYRzSQ2t8W5s+fn0aY1/42gWOIh9i1vy3g+OE4an9bQP7hGK5bty678a9Cf0R+NMBH5E8//fSSv+2IgNPHuA1Az0ibnwQcfqnkgmAoSO33QJz2ecivYvwi0/M85A6c9ntAGeNOjPZ7yB0D7feQu4za7zFx4sS0j9rvIb+Ktb8OiIvWDfZT+z1EwGm/B86byDmDusHx134PuWOg/XXAPuaWNXrOgGg+IQ71o/0euHMzadKkkt+j6XySO9PaXwe5A6f9HtF8QlwknxAnd+9ywPHDcdR+j+i1RvKpqbrB9tIduDVrhkXAkdFDBJw+xv2InDMSF8knnNeRdgZ6Rtp8dqEasAvVBnHRuomcMyLgtN+DXag20XxCXG45AbtQbZrOJ2lwtN9jvHShiun5ZHAYV12oeoE6RBJE4rTPgwLOhgLOhgLOJppPiMstJ6CAs2k6n6INTtsF3P7779956qmnKOBaAAWcQyRBJE77PCjgbCjgbCjgbKL5hLjccgIKOJum8yna4LRVwO2zzz7dD68XTS9HBgcKOIecBNFx2udBAWdDAWdDAWcTzSfE5ZYTUMDZNJ1P0QanrQLOMr0cGRwo4BxyEkTHaZ8HBZwNBZwNBZxNNJ8Ql1tOQAFn03Q+RRuctgk4z/TypJeLLrpozNYVBZxDnQSpIlJJFHA2FHA2FHA20XxCXG45AQWcTdP5FG1w2iTgMLyGZzqG9EIB9+e4SD5RwNWAAq4aCjgbCjgbxOWWE1DA2TSdT9EGpw0Cro5wE9Oxo0nx4/ZFW7x4cc9yjzzySM98vJTx5ptvpr+yDK6LVVZcD54JxEfqzzzzzJ5lPvvsszQf12NtxxxzTKncowUFnIOVIB6RSqKAs6GAs6GAs4nmE+Jyywko4GyazqdogzPoAq7qRYV+ptc5mmzatCmV6Xe/+13nhRde6Hz88cdpGoKqmI9i+EA9Pi4vVhRwGzduTD7EvvLKK92vNTz99NPdZYp1hW2+9tpr3WkcD3yeCwJPDCLxgAMOKJV7tKCAc6hKkDpEKokCzoYCzoYCziaaT4jLLSeggLNpOp+iDc6gC7gq8GUJy/Syo8XChQuTyDr++ON7/CeccEIqp3xp4fXXX0/Te++9d3eZlStXJp8IuC1btqRpfDGkuK4FCxYkP+7gYVoE3F3r13eXueSSS5IPdzExzS7UP8dF8okCrgYUcNVQwNlQwNkgLrecgALOpul8ijY4bRRwV1x+eefaa69NQ4mIvfXWW9mNf5Pg84noOhXBJgLu008/TWUvLos6hImAE9PrlHm4a4f/RcDtsMMO3fkHHnhg8kEUYpoC7s9xkXyigKsBBVw1FHA2FHA2iMstJ6CAs2k6n6INTtsE3KpVq3oa+f/93/9N02NNwKH+nn322T8qpT8ZxFpRwO2xxx7p/1tvvbUUD1GmBZxluNOH5SDg5H8B5zfsu9/9bpqmgPtzXCSfRl3AoYHUfo9IJY0HARdtcCZMmEABZ4AyRs6Z0RJwuckcPWdANJ8QF6kbNPz4lqb2ewwln6IX1cj2QNMCDnGRfIo2OPItVO33GKsCTouPr3zlK2l6rAm422+/PZXn448+6tx5552pAYf/kEMOSX4IOHnJYcOGDT2x1h24RYsWVYLuWiw3XgWcd85UEc2nqICTb6Hi/yTgUIC2gv2bPXt2yd8WkLjj4RhCwGl/m8A+Tpw4seRvC/Pmzetst912JX+bwDHEs0Xa3xZw/HActX8QOfHEEzvvvvtu5/Of/3zXh/zDMXz77bezG/+R5JNPPimVB42/vFggXahS7i996Uvd5eQunQg4ebEBbWJxfSJ4Hn744TTdFgGnj3sbwAsk0uYP6Q5cVK1qn8d4uAMHInHsQrVhF6pNNJ8Ql1tOwC5Um6bzCduL3DFoUxcq3uo844wzenwoJ47hWLsDt3nz5lSeFStWpGsaXjh49dVXu+LpW9/6VlruuOOOS9O4U4f9P/zww7vLiIA77bTT0jReZpBjefDBB6cYmLxJWkfAof7EIteEkSR6B0776hDNp+gduGHrQu2XIBaRSqKAs6GAs6GAs4nmE+Jyywko4Gyazqdog9MWAff+++9XNu4i4NZ873uV80cT6UYVw5AfuGMoJsvhrpiIMQgwCDLcwYMgk2WqxoGTlxeEBx98sCTgcA2GXXXVVV0fyiHGceDK8/pBAVcDCrhqKOBsKOBsEJdbTkABZ9N0PkUbnLYIONiPfvSjkn8sCzhwzjnnpBcvinmLu2foDtbLYj/k+gfTLzdMmzYtDUuyZs2a9DfyPLuAcwIvUQxlHcMNBZxDvwTpR6SSKOBsKOBsKOBsovmEuNxyAgo4m6bzKdrgtEHAybhvBx10UGneWBdwHrfddlt6W7UopKRb9Rvf+EZp+TZDAedgJYhHpJIo4Gwo4Gwo4Gyi+YS43HICCjibpvMp2uAMuoDDALcw3C3Sy4NBF3Bf/vKXU7lhL774Ys+XGPSybYcCzqEqQeoQqSQKOBsKOBsKOJtoPiEut5yAAs6m6XyKNjiDLuBWXXdd30Z90AUckE9sieE5tpNOOqm0XNuhgHOoSpA6RCqJAs6GAs6GAs4mmk+Iyy0noICzaTqfog3OoAs42AUXXFBaVmiDgCN/hALOoSpB6hCpJAo4Gwo4Gwo4m2g+IS63nIACzqbpfIo2OIMs4I499tjOO++8k97c1MsKFHDtgQLOQSdIXSKVRAFnQwFnQwFnE80nxOWWE1DA2TSdT9EGZ1AF3FlnnVWrMaeAaw8UcA7FBMkhUkkUcDYUcDYUcDbRfEJcbjkBBZxN0/kUbXAGUcBtu+225rhvGgq49kAB5yAJov0ekUqigLOhgLOhgLOJ5hPicssJKOBsms6naIMziAJOrGrYEM1YF3Cwxx57rORvO7Czzz675O8HBZyDJIj2e0QqiQLOhgLOhgLOJppPiMstJ6CAs2k6n6INzqAKuGuvvbY0vwoKuLEJ7NNPPy35+zGuBBxEQC5TpkxJD4Rqfz8mTJiQ4rTfA9tBHG6H63ke2L85c+aU/B7bbLNNumBpvwfKGNlH1A0+TK/9HlOnTk37qP0ekyZNCpUTIC5SN9g/7Kf2e2D/dt1115LfA+dN5JxB3QDt98A5E61T7CPitb8f0XwC0XxCXKRuMIAqPhyu/R44ZyL7GM0nudZofx1wDGfOnFnye0SupSCaT9hepG5w/HActd8jeq2Ra2mkbhD3PzfemD77pOdZIP9wDG+++ebsxr8JxquAO/XUU9O+5/yIFwGnj3E/hpJPkWsp2tDcaz6AnpE2Pwk4QgghpC2cfvrpqQE/5JBDSvM88JktT8DttttuaUiSnXfeuevDHX/48MF48X3pS19KPjTy4oMQWblyZefXv/5156c//WlqiIvrPvfcc1MM7tBceuml3TuIVQIOyxWHRkHjvnbt2s5LL73Uuf/++3u2C1A2lB0CB19ueP755zuHHnpozzLCLbfckr51iu+oygfsNQsWLOisXr26s2nTps6jjz5aebcUAyc//PDDaT2zZ88uzQcQaRh8GNvDMSvOQ71ifDvUlY6zEAGnj23bYBeqAbtQbaLdGtEuH+xfzq8vgV2oNtF8QlxuOQG7UG2azqdol88gdaHC3n3nnZK/HzldqCgXBsndvHlz13fjjTemuGLsli1beqbFEPvkk092X7CoWkYMwkb8IuAgDGXQXggo+PBdVBjW/bOf/SyVDVbsfiza66+/3nn33Xe707IM1gf77LPP0qe5il90wDaq1oXlPv7oo/T/m2++WVrmlVde6bzxxhvdaZn/8ssvd32oD6xHLwOWL1+efIcddliP32JcdaHqBeqAQkcvHtrnQQFnQwFnQwFnE80nxOWWE1DA2TSdT9EGZ9AE3Jlnnlny9yNHwIFXX301iSXJB9yFEpNlitO4GwaDMNp///0rlylOQ3hhH3AdEz8EHB4nEfFWvDP20EMPJV+ddaO7UHzYB5i0I2+99VaanjVrVncZfPQehrt7mMajO2IQS/DhWIlheunSpen/osgVMbho0aKe8uCOoV5GpgFEC+yu9et7/BYUcA4odPTioX0eFHA2FHA2FHA20XxCXG45AQWcTdP5FG1wBkHAybAhxx9/fHbd5Ao4XJNgeGYOogl2xx13pL/SLQqTO2AvvPBCEks676655pq03De/+c1uDExvDwbRKLZq1aqe+eiihP3ud7/rEV96Haifog/HFYbuVL08wDdkZd34Cx/2BYbu2OKy55xzTue8885Lxwy2cePG0vogPiHS8H/RDj/88L7HGvbee++V/FVQwDmg0LkJInHa50EBZ0MBZ0MBZxPNJ8TllhNQwNk0nU/RBmcQBNxFF12UGm7E5dZNroADMIiq66+/Pv0PQQNbtmxZdz6e68L/EE7oUtXrQLcg7Pbbb+/GwPRy2rQ4QtmLBiF31FFHldYhXbJFIKrQnSrTaFfQFQrxWTQRcBBSEKN6PbosWAbrLgLDXUgsh+f0ioblIWhnzJhRWifsk08+KfmroIBziCSIxGmfBwWcDQWcDQWcTTSfEJdbTkABZ9N0PkUbnEEQcDA89I+43LqJCjgYBInE/PznP++8/fbb6WUEmHRXQlDBr9eBO0+wFStW9KxTLweDwDnyyCO7y+AtRr0c9mP9+vVpW2LFdYigLAJhJXfgxPDSwMknn9zThSsCDvsid9Gq+PKXv5yWf/zxx1N3qWbhwoWlGOz/L37xi+72sY7ifFi/bRahgHOIJIjEaZ8HBZwNBZwNBZxNNJ8Ql1tOQAFn03Q+RRucsS7g0NUHw1uPiMutm4iAk+fHxOBDFyIMD+TjwX1ZFg/yQ+jpvJNu1yOOOCJNF9dVBAZBhP8hEmF4WQHTWOeVV16Z6qCqfMV14JuwxWXQ3Qq78847ze3juTuYCDjsC9atcxp37GQfYVXdsvi0GYQh/scwL6iv4ny8zADDvKIfVnxBoh8UcA6RBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naIMzlgUchp6AYRgNTCMut24iAg6iSaw4zIVYUVBNmzYt+SB8TjrppOTDGHdiOlZvC1YcRuSSSy5JPtwNwzRePsC6TzjhhO4yxTuDxXUfcMABaRrXSDG5HojJc3wbNmzo+p544onkw11FGLZ3yimnJB+GKIHJM38yXew2ljdVZftixW7dp556KvmWLFnS9eG4wPRzfxYUcA6RBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naIMzlgUchEWxwUZcbt1EBNxOO+2UloVh7Dnxi+nli/bBBx90/y8+nC9WFavHgSsuW+xaxZufIt5kvt4+5hfvIMoy4kvPr/1JcNVZl5g8/1dc5qM/rEeef4PJfBnqBAahh3rQywB0r8L0SxMWFHAOkQSROO3zoICzoYCzoYCzieYT4nLLCSjgbJrOp2iDM5YFHKzYNYi43LqJCDggw15gaA3xiellMWBtUezA8ExasX7EdCzskUceKflg6OLEtF43RJMWlhCBRcOLAWeccUZ3Gdw5K64Hd/Yw7pyYLIcXJPRLDnI3TpCvWoihrlAHMh/nE4YQ0fbMM8/0rOe5555LIrDo6wcFnEMkQSRO+zwo4Gwo4Gwo4Gyi+YS43HICCjibpvMp2uCMVQGHZ6r0m5WIy62bqIAbJGAPPvhgyT+WkTHocq5XFHAOkQSROO3zoICzoYCzoYCzieYT4nLLCSjgbJrOp2iDMxYFnIz7dvTRR/f4EZdbNxRwYxPcIcw9HhRwDpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4GyazqdogzMWBZyY9iMut24o4MYmsOLXJepAAecQSRCJ0z4PCjgbCjgbCjibaD4hLrecgALOpul8ijY4Y1XAycfeiyAut27Gg4DDoME77LBDyT+Wsb4q0Y9xJeBQgLaC/Zs9e3bJ3xbwfb3xcAwh4LS/TWAf0UBqf1uYP39+Z7vttiv52wSOIUaQ1/62gOOH46j9o8UNN9yQhvHQ/ijIPxzDdevWZTf+ZGwhAk4f4zYAPSNtfhJw+OWRC4KhHrXfA3Ha5yF3NqBy9TwP7N/MmTNLfg9sC78Atd9DKln76xCJmzRpUvfuTQ7y61b764C4aN1EzhkRcNrvgW1FzhnsW2T/5G6R9tcB+7jVVluV/B7R7UXzKXrs586dm8aO0n6PpvNJrjXaXwccQ/w61n6PaF5EyxmtUxw/HEft94heaySfqupGPj+Fu0l6HohsD/mHY3jTTTdRwA04IuD0Me5H5JyRuEgs8iJyDYaekTafXagG7EK1QVy0biLnjAg47fdgF6pNNJ/kQqX9HuxCtWk6n7C9SJfPWOpChb37bu8XBYogLrduUE4cwzZ3oY4XxlUXql6gDpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4GyazqdogzPWBFxx7DIN4nLrhgKuPVDAOUQSROK0z4MCzoYCzoYCziaaT4jLLSeggLNpOp+iDc5YEHDWsCEaxOXWDQVce6CAc4gkiMRpnwcFnA0FnA0FnE00nxCXW05AAWfTdD5FG5yxIOAuuvDCWg0z4nLrhgKuPVDAOUQSROK0z4MCzoYCzoYCziaaT4jLLSeggLNpOp+iDc5YEHCwqmFDNIjLrRsKuPZAAecQSRCJ0z4PCjgbCjgbCjibaD4hLrecgALOpul8ijY4oy3g9t5779Qo77HHHqVlNYjLrRsKuPZAAecQSRCJ0z4PCjgbCjgbCjibaD4hLrecgALOpul8ijY4oyngDjnkkNQgz5kzp7RcFYjLrRsKuPZAAecQSRCJ0z4PCjgbCjgbCjibaD4hLrecgALOpul8ijY4oyngnnjiiawGGXG5dUMB1x4o4BwiCSJx2udBAWdDAWdDAWcTzSfE5ZYTUMDZNJ1P0QZnNAUcrN+wIRrE5dYNBVx7oIBziCSIxGmfBwWcDQWcDQWcTTSfEJdbTkABZ9N0PkUbnNEScGeffXbnxRdfLM3vB+Jy64YCrj1QwDlEEkTitM+DAs6GAs6GAs4mmk+Iyy0noICzaTqfog3OaAi4Sy65JLshBthebt1QwLUHCjiHSIJInPZ5UMDZUMDZUMDZRPMJcbnlBBRwNk3nU7TBaVrA7bLLLqkRzm2IAbaXWzcUcO1hXAk4rCQXaQC03wNx2ucht9Ijsdg/fPxV+z1wQKL7FymnxGqfxzbbbJP2Ufs9pGHU/joM5dhH4kTAab8HtoX91H4PxETjonWKfYQY136P6PbkoqP9HtG4efPmdaZMmVLyezSdT3Kt0f46yI9F7feI5kW0nNE6xfHDcdR+j2herLzqqtQIX3/99aV5HpHtyY9hfsx+8BEBp49xPyLnjMRFYqPtk3zMHv8nAQclmAsKjDsV2u+BOO3zkF9w2Fk9zwP7N2PGjJLfA5WL7Wq/h1ystL8OkTj8Ko4cQxz8yPYA4qJ1EzlnRMBpvwfKGDlnJFG030Maf+2vA/Yxt6xyF1X76xDNJ7lQab/H3Llz02eQtN9DLo7a7xGtG7nWaH8dcAynT59e8ntE82ko1+DIPuL44Thqv0f0WgO78sorG6sb5AOO4dq1a9O2v//975MBBqaPcT8i56jERa6lOK/RZmi/B/SMtPnsQjWQRkr7PUTAaX8dInHsQrVhF6pNNJ8Ql1tOwC5Um6bzSRoc7fdosgtVxn374he/GKobbC+3bnQXKm3wTR/jfuSeo8W4SD7hvEabof0epS5UvUAdIgkicdrnQQFnQwFnQwFnE80nxOWWE1DA2TSdT9EGpykBd+yxx6bGd+rUqeG6QVxu3YiA0/46YHuRxhjbxPVG+z3kbr/2e+A6GtlH1GXknBlKPiEuUjfz589P7aL2ewylnNG6iZwzFHA1oICziV5Uow0OBVw1UZECovmEuNxyAgo4m6bzKdrgNCXgNm3alARc8ZEEvYwH4nLrhgLOhgLOJppPFHA1oICrhgLOhgLOBnG55QQUcDZN51O0wWlCwOE5O9jRRx9NAdcHCjgbCrgaRBJE4rTPgwLOhgLOhgLOJppPiMstJ6CAs2k6n6INThMC7qILL+z86Ec/Sv9TwNlQwNlQwNUgkiASp30eFHA2FHA2FHA20XxCXG45AQWcTdP5FG1wRlrAXX755T0PnlPA2VDA2VDA1SCSIBKnfR4UcDYUcDYUcDbRfEJcbjkBBZxN0/kUbXBGWsCJyTQFnA0FnA0FXA0iCSJx2udBAWdDAWdDAWcTzSfE5ZYTUMDZNJ1P0QZnJAXc4sWLk3ibM2dO10cBZ0MBZ0MBV4NIgkic9nlQwNlQwNlQwNlE8wlxueUEFHA2TedTtMEZSQG3YcOGzne+850eHwWcDQWcDQVcDSIJInHa50EBZ0MBZ0MBZxPNJ8TllhNQwNk0nU/RBmekBJwMG6L9FHA2FHA2FHA1iCSIxGmfBwWcDQWcDQWcTTSfEJdbTkABZ9N0PkUbnJEScLAXX3yx5KeAs6GAs6GAq0EkQSRO+zwo4Gwo4Gwo4Gyi+YS43HICCjibpvMp2uCMhIDDsCGPPvpoyQ8o4Gwo4GzGnYDDxnORQucylLhILPZv1qxZJb/HH7dX9ntEyymx2ucxefLktI/a79F0OYcSJwJO++sQ2Wa0bqJxAPs4ceLEkt8jur1oWaNx8+bNS59G0n6P6PYkVvvqEI3DMcSHprXfI7q9ocRFYnH8cBy138Pa3i677JLuvh166KGlef3i6hCJQ/5FrqUgWtam40TAaX8dItsbalwkdscdd0ztovZ7RLYlcZFY6ItIHPSMHMMk4KCuc8GGoSC13wNx2uchKh6/OvQ8D+wf7sBpvweUMdS/9nv88cDk7yOIxE2YMCHto/Z7yK9i7a8D4qJ1g7ti2u8hAk77PXDeRM4Z1A2Ov/Z7yK9i7a8D9jF3m3JnWvvrEM0nxKF+tN8Dd24mTZpU8ntE8ylaN3JnWvvrgGOIO3Da7xHNJ8RF8glxqFft98Dxw3HUfg/rWiOm/ULxDpye5xGpG+Rf5FoKovmEbUbyKXqtEQGn/R6oy8g5M5R8il5rcAcO7aL2ewylnNG6yb3mA+gZOYbsQjVgF6qNXFS130NOcu33EAGn/R7sQrWJ5pNcVLXfg12oNk3nkzQ42u8x3F2osNWrV5f8ArtQbdiFajPuulD1AnWIJIjEaZ8HBZwNBZwNBZxNNJ8Ql1tOQAFn03Q+RRuc4RRwVcOGaCjgbCjgbCjgahBJEInTPg8KOBsKOBsKOJtoPiEut5yAAs6m6XyKNjjDJeCWLVuW7r555wMFnA0FnA0FXA0iCSJx2udBAWdDAWdDAWcTzSfE5ZYTUMDZNJ1P0QZnuAScNe6bhgLOhgLOhgKuBpEEkTjt86CAs6GAs6GAs4nmE+Jyywko4GyazqdogzMcAm6bbbZJ4u3oo48uLaehgLOhgLOhgKtBJEEkTvs8KOBsKOBsKOBsovmEuNxyAgo4m6bzKdrgDIeA6zfum4YCzoYCzoYCrgaRBJE47fOggLOhgLOhgLOJ5hPicssJKOBsms6naIMzVAF3+eWX1+o6FSjgbCjgbCjgahBJEInTPg8KOBsKOBsKOJtoPiEut5yAAs6m6XyKNjhDFXBier4FBZwNBZwNBVwNIgkicdrnQQFnQwFnQwFnE80nxOWWE1DA2TSdT9EGZygCbsmSJUm85cRTwNlQwNlQwNUgkiASp30eFHA2FHA2FHA20XxCXG45AQWcTdP5FG1whiLg7r//fnfcNw0FnA0FnA0FXA0iCSJx2udBAWdDAWdDAWcTzSfE5ZYTUMDZNJ1P0QYnKuDqDhuioYCzoYCzoYCrQSRBJE77PCjgbCjgbCjgbKL5hLjccgIKOJum8yna4EQFHOyll14q+T0o4Gwo4GzGnYAjhBBChpsbb7ih8+yzz5b8hJChkwQcVHlbwf7ttttuJX9b2HXXXdM+an+bkJNV+9tE2/cPOYhzVfvbBI5hm/cR+5ZzLV28eHG6+3bKKaeU5o1V2p6H4+Fa2vZrDfZPjiG7UA3YhWoT7daIdvnIyar9HuxCtYnmE+JyywnYhWrTdD5Fu3xyulD32muvP44Z8gfD+RKpU3ah2rAL1WbcdaHqBeoQSRCJ0z4PCjgbCjgbCjibaD4hLrecgALOpul8ijY4OQJu1XXXJfG2evVqCrg+UMDZIC5SNxRwNYgkiMRpnwcFnA0FnA0FnE00nxCXW05AAWfTdD5FG5wcAQeTYUMo4Gwo4GwQF6kbCrgaRBJE4rTPgwLOhgLOhgLOJppPiMstJ6CAs2k6n6INTl0Bt2zZss67777bPd4UcDYUcDaIi9QNBVwNIgkicdrnQQFnQwFnQwFnE80nxOWWE1DA2TSdT9EGp46AW758ebr7VvRRwNlQwNkgLlI3FHA1iCSIxGmfBwWcDQWcDQWcTTSfEJdbTkABZ9N0PkUbnDoC7r333qOAy4ACzgZxkbqhgKtBJEEkTvs8KOBsKOBsKOBsovmEuNxyAgo4m6bzKdrgeAJu3rx5SbwddNBBPX4KOBsKOBvEReqGAq4GkQSROO3zoICzoYCzoYCzieYT4nLLCSjgbJrOp2iD4wm4yy+/vHPXXXeV/BRwNhRwNoiL1A0FXA0iCSJx2udBAWdDAWdDAWcTzSfE5ZYTUMDZNJ1P0Qann4CTcd/23HPP0jwKOBsKOBvEReqGAq4GkQSROO3zoICzoYCzoYCzieYT4nLLCSjgbJrOp2iD00/AiWk/oICzoYCzQVykbijgahBJEInTPg8KOBsKOBsKOJtoPiEut5yAAs6m6XyKNjiegJNx3zQUcDYUcDaIi9QNBVwNIgkicdrnQQFnQwFnQwFnE80nxOWWE1DA2TSdT9EGxxJwm15+uXPGGWeU/AIFnA0FnA3iInUz7gQcGrpcpHK13wNx2uchYgOVpOd5YP9mzJhR8nsgQZBc2u8hDY72e8iJrv0eEydOTPuo/R5yUdX+OiAuWjfYT+33EAGn/R44byLnDJIKaL+HXFS1vw7Yx9yyRs8ZgDiUV/s9pKHSfg80/Ntss03J74HtRfYxWjdyrdH+OuAYTp8+veT3GMq1NJJP0TrF8cNxLPrOOuusdPdNL1tEfthov4fkU1N1g/yLXEtBNJ+i15poOyMCTvs9UJe51ycwGu0MBBzaRe33iJwzEhetm8g5M2P77bvHMAk4rCQXOWFzGUrcVltt1Tn44IOz+M///M/OUUcdVfKPFIsXL05ofx0icUuWLEn7qP11iGxvuOL08e2HCDjt95CLnPZ7IA5ov4c0jNpfB+zjhAkTSn6P6Pai+RQ99hid/z/+4z9Kfo+m82koccjDpUuXlvwe0e1F8yl6nk6ZMiUNFVL0wR5/7LHSskWieRgtp8RqnwfyD3n4ta99rVTXHkM5TyNEt3fSSScNZHuRw7HHHpvaRfyvj3E/IueMxEVio+3MrFmz0nmK/weuC5XWDtPHuB8i4LTfA+cNzhnt9xhPXai0dpg+vv3AsY90+eguVGvcN82gdaGu+d73VO3SBtX0Me5H5ByVuEg+DVsXql6gDpEEkTjt89ACbrfddistQwaDb37zm9mJRQFXzXAJOObT4BLJp2iDUxRw/YYN0QyqgNPzyeDw1a9+NfsYRs5RiYvkEwUcGTgiDQ4FXDUUcCSST9EGpyjgVl13Xe3tUsCRpqGAc4gkiMRpnwcFXHuINDgUcNVQwJFIPkUbnKKAg1nDhmgo4EjTUMA5RBJE4rTPgwKuPUQaHAq4aijgSCSfog2OCDi8kPLuu+/WHhaGAo40DQWcQyRBJE77PCjg2kOkwaGAq4YCjkTyKdrgQLBdfPHF2dujgCNNQwHnEEkQidM+Dwq49hBpcCjgqqGAI5F8ijY4EHAffPBB9vYo4EjTUMA5RBJE4rTPgwKuPUQaHAq4aijgSCSfog0OzhPYvzvDhmgo4EjTUMA5RBJE4rTPgwKuPUQaHAq4aijgSCSfog3O1Vdf3XnggQdKfg8KONI0FHAOkQSROO3zoIBrD5EGhwKuGgo4EsmnSIMjw4ZUfQvVgwKONA0FnEMkQSRO+zwo4NpDpMGhgKuGAo5E8inS4IhRwJFBgALOIZIgEqd9HhRw7SHS4FDAVUMBRyL5lNvgyLAh22+/PQUcGQjGlYBDg5ULCo0TXvs9EKd9HnIBQCWxwRlspMHRx7gfIuC03wPJgXNG+z3QcADt98C2Iuc3wD7mxkpeaH8dmE/tIJJPOPY5582mTZs6y5cv72y77baduXPnluZ7iBDTfg/JJ+SxnucRaZ8Qgzxcu3ZtduNPxhYi4PQx7kfkHJW4SGy0fZoxY0Y6T/F/EnBSgEGADc5gIw2OPq79EAGn/W0C+4hhGrR/pGE+DTaRfMrhv//7v7vr32677Trz588vLdMWkH/Iw3Xr1qV91nVNBgcRcPoYt4HZs2d3f/CzC5U0SqTLh12o1bALlUTyCce+bpcP7NFHH03/Fz+llQO7UEnTjKsuVL1AHSIJInHa50EB1x4iDQ4FXDUUcCSST3UbnHnz5qV1//u//3uapoAjgwIFnEMkQSRO+zwo4NpDpMGhgKuGAo5E8qlOg7PXXnul9e65555dHwUcGRQo4BwiCSJx2udBAdceIg0OBVw1FHAkkk91Gpzr/jTuW9FHAUcGBQo4h0iCSJz2eVDAtYdIg0MBVw0FHInkk9fg3HPPPWmd3/nOd3r8FHBkUKCAc4gkiMRpnwcFXHuINDgUcNVQwJFIPnkNDgzjvkGwFf0UcMPHggULOosXL+7hwAMP7EydOrW07FCQdWt/26GAc4gkiMRpnwcFXHuINDgUcNVQwJFIPvVrcDDe24svvljyAwq44eOdd95J27DspZdeKsVEENP+oYBzAIZv4+p5mqr9/OSTT0rLDTcUcA6RBJE47fOggGsPkQaHAq4aCjgSySerwdlmm2067733Xufoo48uzQMUcMOHCBvcdRNWrFiRhmwR0zERnn/++YT2D4Uddtghle/6668vzSsyefLk7r5AkD799NPd6ch5lAMFnEMkQSRO+zwo4NpDpMGhgKuGAo5E8slqcMS0X6CAGz5EwGk/0Mfhggsu6Jx55pmdhQsXdu69994koGQeukfXrlmT7pri2UW9rtNOOy2h/atWreo8/vjjKUZ3lQurV6/ubNy4MYnKb3/72z2xsGeffTaVbd999y3Fgt/+9rdpuWnTpnV9EHW///3vO7/73e9Kyw8nFHAOkQSROO3zoIBrD5EGhwKuGgo4Esknq8GBXXvttSW/QAE3fPQTcBA4xXmwzz77LP2F7b///smP8mp7/fXXe66VYjKNZ+xwN6xo2N6JJ57YU4Yrr7yyZxmYHHttd999d2kfwEcffZTQ/g8++CDFaf9wQgHnEEkQidM+Dwq49hBpcCjgqqGAI5F8qmpwMGzI/3fZZaVli1DADR9VAu6AAw7orFmzJvmL88TQBbn33nsn35IlS5IP65EXH3C9E9Oxerp4rRHBKNdKEYsQQZhGXb7xxhvJt88++9TuQq1C3nB+7rnnSvOGEwo4h0iCSJz2eVDAtYdIg0MBVw0FHInkk25w0A0H88QZBdzwIQIOYkkoGu5SybJixfjXXnst+Xbaaace/8cff9yzbDEW37KFvfXWWz0xK1euTH68wKJjhOOOOy75cIc2KuC23nrr7roj1/McxpWAw0pykQZA+z0Qp30eksgAxgZncJEGRx/jfoiA034POW+03wPJCLTfAzGR7QHsIy5w2u8R3d4f8+lzzKcBJ5JPci2VaRiGDdHLaaZMmZI+r6X9HtG8wPnZZDuD/EMe3nTTTalOdF0PJyLgcMdNwDNnp556amlZMZnGyybaJ9x6663Jf/jhh5dir7jiivT/p59+moReEZi8fQzDXTm9biFXwO2+++5/LMQfbMuWLekunl5muBEBp49xPyLnjMRFYnFeR9qZmTNnpvMU/ycBJwUYBGBscAYXaXD0ce2HCDjtbxPYR9zh0P6Rhvk02ETySQM7++yzS34N7uDMnz+/5G8LyD/k4bp161Kd6LoeTqq6UC3EZBovDWifcOmllyb/UUcdVYqV7kvLXnnllW4MBL1et5Aj4C666KJuFy2Eo54/UoiA08e4DcyePTudp/ifXaikUSJdPuxCrYZdqCSSTzj2+OUvw4Z8/etfLy1TBbtQh4+hCDigX3QQNm/enPy49ulY6QbFCwrFGNQzfIsWLerG6DtwO++8c+rmxV3CugLuyCOPTMs1Me6bZlx1oeoF6hBJEInTPg8KuPYQaXAo4KqhgCORfJIG58ILL8yKpYAbPoYq4N58883k07mrly1Oz5kzJ/3//vvv98TccMMNyY+hSnSMIOPTHXHEEbUF3DPPPJOEoDXMyEhCAecQSRCJ0z4PCrj2EGlwKOCqoYAjkXySBgfWb9gQDQXc8DFUAQcwQK/YRx991P0f47tZsR8Xlvvwww97Xp6QZc4///yuT+70wZYtW9ZdBiJQbP369aWyoZuvn2G7OmY4oYBziCSIxGmfBwVce4g0OBRw1VDAkUg+4djLc1R77rlnab4FBdzw8fbbb5e6KS3EtL84bIiY/ryVmExjyJGi8IPh2Td9lwzP0BVND7wrz9rBqsaBw+DB/Wykn4ejgHOIJIjEaZ8HBVx7iDQ4FHDVUMCRSD7h2N+werU77puGAm7sMX369PRsG55hO+SQQ0rzxbQfQ4bgbVsIMT1PWLBgQfoCA8Rd1TE46KCDOvvtt1/o2I40FHAOkQSROO3zoIBrD5EGhwKuGgo4Esmn++67LzsGUMANFjLuWxv2JRcKOIdIgkic9nlQwLWHSINDAVcNBRyJ5BOs3zARFhRwg8PFF1+c9gGGcd70/LZDAecQSRCJ0z4PCrj2EGlwKOCqoYAjufn0X//1X+lbmJEGhwJucMBLBMcff3z2NaUtUMA5RBJE4rTPgwKuPeQ2OIACrhoKOJKTTzLuGxr2SINDAUcGBQo4h0iCSJz2eVDAtYecBkeggKuGAo7k5JNYtMGhgCODAgWcQyRBJE77PCjg2kNOgyNQwFVDAUdy8gmGcd+iDQ4FHBkUKOAcIgkicdrnQQHXHnIaHIECrppBEHAYtX3x4sU97L///uFy1+HLX/5y2o72Nw26KvHxd+0fTurm03XXXdcdNiTa4FDA+SxZsqRz1113dacnT57cOemkkzrf/e5307TkwMSJE9M0PvS+xx57lNZDhgYFnEMkQSRO+zwo4NpD3QanCAVcNYMg4B555JG0jSrD6PF6+eFARqXX/ibBuQeThnukqJNPEAwwEV/RBocCzke+dKCn5csDYocffniafuONNzpbtmwprYcMjXEl4AYJ2Eg2OGRkkQZHH1cyOox0PomAQ4O16667Js4+++zOQw89lPywhQsXluKGwngUcPq46mOMTx9pP6nmRz/6Uej8wbkNE3EGYMUvLjz11FMJ+UE6lgWcmPYPAiLg9LFtG0nA4ZdHLvg1hl9I2t8PqE3Eab8HtoO4CRMmpIMykg0OGVmkwdHHuB84R3HB034P/CrCOaP9HvhFtdVWW5X8HltvvXXo/AbYx9xtRvMJIA7lHel8EgH3pS99qTRPPqJ9yy23lOYNhfEo4PTxLQLDyPvFY48uPL2cB7oD586dW/J74LyOnKeST8hjPc8DccgP7e8Hyok8xBcKIufPz3/+8/SN06IPpj8eX4QCbmQQAaePcT+QE7nnDBBtov0eOK9xjmu/x8yZM9N5iv/ZhUoapU6Xj0YEnPZ7sAvVpql86ifg8IwYDHfj9PLainEoe5VJV5sWcDvttFO3K2vtmjVdf/FD3mK4GMv8b3zjG8mnvwsJK5YHY25heI6i3XjjjelvUwLuJz/5SWmeDBvy9a9/vccf7fJhF6rNrbfemmLk2TZ9Hud0oerzctOmTT3n5SWXXNLzkXkYzu9FixalOkM8KNYb/ofvk08+SdfFfuvAtVbbMccck9aDu+Xait9JRTlheA4Qg0WLYVt77713d1qsuN/DybjqQtUL1CGSIBKnfR4UcO2BAq6a8Sbg8HD/hx9+mOYVv+Eo9uyzz3aefvrp7vTBBx/cXQYD0cLQKPzmN7/pNkQ//OEP03wt4DASPWz16tVd3+WXX/7HFf/B0Iji49ow3C3BJ4iwjAg4GOa/+uqr3Wn5+Pe0adO660cDuXnz5u4ysKYEHAzfrSzOu/DCC5Nfx0QbHAo4m7feeqsnBh+Vf/PNN5MP5ydEGPxiloArnpf4yHzxvJRlxLDen/3sZ91zTj4Q/+STT6ZpEV0A/8N+/OMfu+uYNWtWt+ww/H/AAQckJNfww0DyDIbvomK9IuDEXn/99SQaYRL7wQcfdOefe+65PfU4XFDAOUQSROK0z4MCrj1QwFXTdgFn2dKlS3uWx0W++BYf7mjA5A4TGgSYCChhw4YNyb/PPvt0GxbUqTQeaBhl2XvvvTf5ig0cwAUVhgYG0yLg0IDJMhCiMDSSmJa7JfpzRSI+mxRwsOI8GIYN0THRBocCzqaq/sUPcaSXqxJw1nkp53BxHciTqVOndn0vv/xy57XXXutZRgQdECGYuw4dU5wWfvWrXyU/hJ8IOOTFlClT+sbizl2xboYTCjiHSIJInPZ5UMC1Bwq4atou4HAH4vnnn0+gwSp2E91xxx2lOIAyQrjBRMDphkjARe28885LjYgIOGn4Vq1a1bMsGs2qdQAx/C8C7qKLLupZBg0fGq3i8sWuWYCuKFjTAk7uwu21115pes899yzFRBscCjgbsSp/XQFnnZe/+MUvkl/uDItBAOF818sXl/Gmh7IOQb67ipeTRMD98pe/7Lsu8Pbbb/d0vw4nFHAOkQSROO3zoIBrDxRw1bRdwOkuVEFMpvXzP7gjABMBJ6bXU6TYtSMiDmNx6W32MywnAq7YxQuwzhdeeKFnXcUu3uJ2mhZwsI0bN6a/ltiKNjgUcDZiVf66As4ziBIsh1zCHV79DFvxBQp5JhPXQHmhBtuS+XXWIaanLfuf//mfroC7+eabS/UAK/og4PAYRdE3XFDAOUQSROK0z4MCrj1QwFVDAfcXnSOOOCL9j0bl5JNPTi8fwI/piICDaDvyyCPT/xBdMl9EIu6SWWC5HAF36qmn9iyDiyxsNAScGO7GVRFtcCjgbMSq/HUFnHde6msZyrt+/fokhMRknrxEg+3gMQXYZX8ayLnuOqxpXS4Bz4PmCjjegaOAGzZwcdKjxmvw2q+OawsYxwhvBmr/cEIBV814FHD4YoIYpuXha3y9QZa5/fbbk08/A4c32orrwi95CD3sk36JQRpGaTQfffTRNA2BVlyHPG+nn4GrI+CKAhHICw+jKeC0SfdqtMGhgLMRq/LXFXDWeVl8bABlhOHuWXGZ5557rruM8Nvf/jadl4iXLv+cdYhZ0wIej4DNmDGDAi4DCrhh5v777++eaJbpi3mbkIdotX84oYCrZjgEnH4LsR9N5BMQAbdmzZo0dAFYu3Zteq5Hum/wth2W/cEPfpCm5QUBDM8h9sQTTyTfYYcdlqYx5IF8guiu9euTD2+nYloLOGwThsYC+4w3YLFtNGz49BGWmTNnTre7Fm8QwldHwN1zzz1pGZg8o/TAAw90fWNFwBWHGYk2OIMq4PBii55fxVAEnLxRrf2wugLOOi/FiuvAcieccELXJz9SitvGs5tixUcI6q5DTK5L0i17xRVXpGkcH7zVCpN8GIqAQ/ctyjR9+vSe5SJQwDlQwI0seCAbhrsUet5IMVYFHOyaa64p+T3Go4CrW7dN5BPw3kLFr36MV4ZlUQdixU8Qyf9yZ+zxxx/vLid3J2AiLrSAAzLMw913352mcT6JyXNysOJbeHUEHMou5YPJtqUxHAsCTo8RB7vgggtK6/IYZAEH08tohiLg5JzUflhdAQeK5yXEjVjV26EwrLv43Ghx2zg3xXQdFs1aR9HQDYseKPnRheWLz8/h7htihiLgZH+tlypyoIBzaLOAw698Pa9p5NfTfvvtV5o3UowlASdiBIYPcfMOXBkt4ECx3vrdkWsinyJgWINTTjkl3TEoDkOAZ+IwDpVMo+x4cWDFihWhcwPgcQjkOhrNs846qysko+AZIwg23ViOJP0EHISb3H0qnhcQb5EGZ1AFHBARB7PyYigCDmXEUDLFQamjyHmJL5XgvNTzAfIEj7vg7vOVV15p1q+Y9tddB4437nTjWio+1CXy7vzzz+/svPPOpZih8NOf/rTki0AB56ATpC6RShprAu7oo49OF0H8ikIC4C6DzENZ8UDziy++mF6llgEOBdyyll+/aJAwThPGsDrjjDO6y2C+/KLDLxn5dSNgWATMx7pwUS3OQ1IhHicHyomuKv1rSMBD4hBtGALhwAMPHBMCrtjQiLELtZoqAQe06fmgiXwiI08/ASfLaIs2OIMs4IA2HTMUAQdwXcadqbHynDT2B4bnMfW8sQieQdXjKUYZVwIOJ3ouKDQaSO33kMTKATvaRINTV8DJeD3F7hv45duSMDwgimd7ivMBRtQuGm4jy61oedAUA4dKVwyeO5A7D+LDSS6j0YvJ+ouG9RY/Z7Jy5crScnh2A9sr3g7X+zucSIOjj7FlEHQi4HSMB84bnDPa74ELH9B+DxFw2l8H7CPitd+janv9rBg30vlERh4t4JAvOL5VP4RgxbdQ9XnjMWnSpCTgtN9DBJz2exQFnJ7nUbU9GVNQm9QZ8i8JuD/8oIXpuq4DrDiA7mgh13P9bdaxDG4gnHbaaSV/BBFw+hzoR9U5U4doPuFGQeSav/3226fzFP8nAYcCDAqwkWpwRMBBHD322GMlZDkRcDCMfSNvzeGj3LDisvJwq7zdKQIOz9HgDhl8uEUtzxTIr82qLlQxuVNz6KGHdhNV7jSJ4ZkfvFUKH27Dw/AGH6bRNQXDNmXduDCLiW8kkAZHjifuFvYzzBcBp8+FNoF9xB0O7Y9Qp05lWdhI5RMZeYoCDt1POcc+F7ykMX/+/JJ/UMBQF/0M+Yc8XLduXZrWdV0H61m4phFr8hnqsYQIOH0OtAG83CW6jV2oBUTA4RcU7nJpZDkRcBBP4pOP/N50002l9UIoyYCFIuD0MvKrb8GCBWlaCzhrLB88gwDDK+iYFtPrh8kvQ9xSR5l09+Kvf/3rytjhRN8xoI2+jVQ+kZGH+TT8hq+FwHRdk8FhXHWh6gXq0GYBV7cLFd2b4pM31qrGUcN4PDDshyXg8Go2TMa30gJO5leJSxieucNyYnr9Eov/0RWLrlW9DB7ArYodTtjgjB3DHRvYSOUTGXmYT8NvG/40NIyuazI4UMA5UMB1el7/Puecc5Jv2bJlpeXxmrbcwYsKOHm9HGNa6RGwgYxaL6bXDxMBh7IUxafQxO1//RKD9ayOGN54ki5UvS6P8foSQ786lTcTm8gnMvJoAdfv2MPk2EcanEF/iaFf3SAvhvoSAxk7UMA5VCVIHSKVNAgCTk4Y/VFrvNiArlYZCygq4I477rg0jde9i3GoE/gg4jAtptcPEwGHZ+FQJv0Gq3xORccOJ1rACZbhwkoBV40l4CzTg7mOdD6RkadKwMFviRWcA9EGZ9AFnGUy1AoFXHuggHOoSpA6RCppEAQckBHh8SyZ+OQlAxFLdQUchhWB3Xbbbd1lxESU4IFk6yUGvX6YCDj5TmNxOQhF7RsJLAEnVDU8FHDV1BFwehBXoYl8qgJvxVmGF3u8xloeVcAzoXreeEQLuKLJMtqiDU6bBFxVXoykgBPTfjIyUMA5VCVIHSKVNCgCTkahhmHUeD3MCKgr4PBhYDFprIojvsvbrWKyHj1d9BdfbxeDAJT1yl8dO5x4Ak4oCjk8V0gBV6ZKwBXrrd8nhJrIpyr6CTiYfA7LggKul34CzhrIF3frIw3OIAu4Onkx1gTcaHyNZywQqSsNBZyDTpC6RCqpKQE3XODD3RhSBAkYufgIuFjiMz7Y/6J/+fLl6W1XDL6rY3LAcCLo8sXYOzgp9PyRoK6AKwI79thjS36P8Sbg0EhV3VmoYrTySQSc9gO8YQ3zRBz5M/0EnJh0qwqw4lct6jKoAq5uXow1AacfoxkvROpKQwHnQAFHIkQEHM5RCrgyWsBZdxaqGK186ifgZCBs+T4i9ufMM89M/2OQT3w3FV8lwQ8O+XA8wKMERxxxRBpSB182QcOHO9iYhx9TTz31VPrA/OTJk0vbxHrw+St82xQv8ey+++49888999zul00uvfTSzurVq9P0UUcdVVoXfLKsnjdS1BFwYhKDYz+eBFzdvBhOAYev9GBoqLPPPjt9nF0fA4Dt4eU3DOCOgd+PPPLI7jzkQvFrPPL1HiDnLL4AhGVws0BvPwfEY/sQuda3e/GSHHqorr766jSNsU/luesi2F/kKp7LliGxBJw72A8cVzwiJOsrClS5ww7Dsvvuu29pG3WggHOggCMRogKOXahltIDLYbTyqZ+Aw6MLsN/85jdp+s4770xd/MWvhFR1oRYNXxXRhkcdxNDgVcVhHEV5iQdWtQwMw/U8+eST6f9jjjmmp/xier9GkhwBJxZtcAZVwNVlOAQcfjjI0E4Ya1O+niMmyxU/NP+zn/0sfay+uAw+6F78Gg/Oa/jxQXkx3KkunrMYVF6Xpx/4MQJDOZ999tmex3LwnWFZTgz7VXwEAuWTZS6//PKuH48YyeNDeGRIfmwVxRnmYzzSomEZGYMPhn3GN1d1uetAAecQSRCJ0z4PCrj2QAFXzXgXcLhbgZcYYFdddVXyQcCJ4dlQ1E8/ASdfHsEdN7Fbb701+XDnDlYcPkcMjylon55Gg4O7gTincLcPVhSDVbFN0E/AoeuwCO5EjedhRDyGQ8Ct/9OLbLirhm97wiePBhTXia/wwIoDv4vokUdmqrpQf/jDHyZf8ZzF97Zhud88xdd6YBCL4pMB5deuXZumIb5gxUHr5TnuooCDCITJnV0cM9wxh914443JVxRwELDw4S6imKxLT0eggHOIJIjEaZ8HBVx7oICrZrwJOMuk6xOIgEMDJT5LwBVf0MFD37D77ruvZ9tiukwAF1N0t8rdPi9G+9F9Cqv6EstIUiXgINLQaOIOi14eRBscCjgfsbp+AZ9HkpfIRNxUCTgNzll0e8IgrPT8HPAjSb4XK88M4tECmL424S5bUcDB8ANMr1MM/0vuYr+Ky9TNuRwo4BwiCSJx2udBAdceKOCqGW8CDr/0i5x66qmlYywCDs8Dic8ScMWPduM5NhgGvy6uT6zoO+GEEzovv/xyd55eRk9bfnleSb6L3BRawMkLC6hLWFXjH21wKOB8xOr48XwXzpviIwIwT8DJOStdtWIRAYfcQldlccQEmAg43LGGsNRxeGZOCzhY1VeCYFhGchdjmhbXJXfe9br0NnOggHOIJIjEaZ8HBVx7oICrZrwJOO2vQgRcsQG3BByeIZJpEXArV67sWZ+YTBeH5RGTRseKEdCwwXCOATSAuCuhlxtptIArzoPdcccdpZhog0MB51N1HKr88g3rouHzhrB+Ak4GdC+axOUKONylla5PGISkPIsnAg45gk9B6lg8MyoCDue/Z1hOcrfY/Qso4Mrz+lEScCjAoABrssEhw4s0OPq49kMEnPa3CewjGkjtH2mazqexIuAwtiBsw4YNPcvUbUzmzJmT/A8//HDnscceS/9jWB693EhTFHB4a694bC+88MLk18c8Cp6Hmj9/fsnfFpB/yMN169aletN1XQexfn5sC4Zn0Irn9saNG5PfEnDWOSvrzxFweFNUrOjHc6QwEXB4UQIiT4toiD19B66qCxXPs+Ltbfw/GgJOH+M2gO520W1JwOGXTi4I1r46DCUOwJpscMjwIg2OPr79EAGn/XWInG/4NQW03+Mf/uFzoe0B7CO6M7TfI7q90cqnsSLg5K05/TxOcZmq6SK4M4HGR7qf9PwmkHw6//zzS8cYggR3BdE9XXXs9fIeEKjz5s0r+T2QS5HtRcspsdrngfxDHuI5xujxFMP6qvz4H/kGQzdkcRk5jywBZ52zGLIEliPg5E1qWNF/++23J58IuHvuuSdN4/ySZSQvtYDT68JLHDAMao/p0RBw+hj3I3LOSFwkNtrOzJw5M52n+J9dqKRR2IVaDbtQy4ykgJN91yZdo+g6krf7YLpsoDgURNXdhyaok08wjGcn0zj2kS4fdqH64Jwods3L8236QX15ZrI4T3IDQg4vJhS/xgNDfUAMiWG8RG3ywo+YLp+A/SyWTcpc7FKVZasMjxoUBRyeNxUTQQYr5mVdASdvucLwVq8uex3GVReqXqAOkQSROO3zoIBrD3UaHA0FXDWDKOAwblVxSIJ+yN0AGVYBnHLKKclXHPQUJmPHAbnDgc/TFdcnJtPFhgKGRgxvcErDJkM9wHTZ9DqrurWaoE4+wdDgynS0waGAq4cWXhBk+tnK4mcXYRBO2F8RZRguBMvhLp0YpjE4btFwzuI8LZ6zWE5Ml60IBsQuCjZ06eKtVh176KGH9oyliLtxGK9N3/GT3BSTfdLzi2+VA1036HIVu/vuu0vlrgMFnEMkQSRO+zwo4NpDnQZHQwFXzSAKuDaB4wXLHX9rOKmTT1/5ylfSMrvsskuajjY4FHCDgwwtov25nH766Z1NmzZ1x1gEeBYSgrHO58lGCwo4h0iCSJz2eVDAtYc6DY6GAq4aCrjRBW/xwfSwCE1SN5+K48JFGxwKuMEBhi8raH8u8tYrXrAQn3z9Ac/e6eXHChRwDpEEkTjt86CAaw91G5wiFHDVUMCNHmIYNFjPa5KcfIJhWJFog0MBNz6RLzYUDc+n6uXGEhRwDpEEkTjt86CAaw85DY5AAVcNBdzogeeAlixZUvI3TU4+/d///V9aNtrgUMCNXyCI8DzatddeG7qmNg0FnEMkQSRO+zwo4NpDToMjUMBVQwFHcvIJx3vz5s3p4fVIg0MBRwYFCjiHSIJInPZ5UMC1h5wGR6CAq4YCjuTmE94ExPh1EyZMKM3zoIAjgwIFnEMkQSRO+zwo4NpDboMDKOCqoYAjkXyCFYcVqQsFHBkUKOAcIgkicdrnQQHXHiINDgVcNRRwJJJPP7zrruwYQAE3uixevLiz0047lfxtBsf++uuvL/k9KOAcIgkicdrnQQHXHiINDgVcNRRwJJJPOPZr16zpDitSFwq40QWG7+5qf9uBYTBk7e8HBZxDJEEkTvs8KODaQ6TBoYCrhgKORPIJx36PPfZIcfKdzTpQwI0usPEo4PDiTe7xGFcCDgUYFGBscAYXaXD0ce2HCDjtbxPYRzSQ2j/SMJ8Gm0g+CcVhReqAEfjnz59f8rcF5B/ycN26daledF0XQc5ccMEFnZ133rnrww9G+PCWr/jwaSr4pkyZ0vXhWobv9P7617/u/PSnP+1svfXWPevGd2sRgwYen5XC0B3ww7SAw3JApufMmdNZu3Zt56WXXurcf//9PdsFKBvKDoFz2223pU9i4VNZxWWEW265JX3KC19cwJcd9HyAT3vhTi6+1vDoo49Wim38WHj44YfTembPnl2aD0499dTOiy++mLanv5WKesUzm6grHWchAk4f4zaAOhTdlgQcfnnkgmCoR+33QJz2ecidDahcGBucwUUaHH2M+yECTvs9cN7gnNF+D/zyB9rvgW1Fzm+Afdxqq61Kfo/o9phP7SCST9IQYCy7nNjJkyd35s6dW/J7yJ007feQfGqqnUH+IQ9vuummVC+6rouceOKJaZkf/OAHXd+iRYuSrxh7zz33pOnp06enadS5fLdUDN8zXbp0aTdG7I033kh/IY7EXxRweB5OTHxV60a5iut+8MEHe5aB6c9iPfLII3qRzlVXXdWzzJVXXqkXSd9yLd6lxcDR2iAcZT6+GytfdigaxGdxWxBv+LZqlUCsQgScPsb9iJwzEheJjbZPM2fO7PbYsAuVNEqky4ddqNWwC5VE8knEO/7HsCKvvfZaOuf1chp2ofaCb+BCMEneQmiJyTLFadwNg0GI7L///pXLFKfx3NeZZ56ZrmPih4DDd0nlA/DFO2MPPfRQ8tVZN8S4+ET0iRaQLy/MmjWru8yaNWuSD3f3MD116tTuuiCW4EOdi2EaohSGLlBZDz7vBRNRKYY7hnoZmQboNoTdtX59j99iXHWh6gXqEEkQidM+Dwq49hBpcCjgqqGAI5F80g0ODN12ejkNBVwv11xzTVrusMMOS9MQZiKGZBkx/I8uSRjuwhXXg25MmDyPKKY/0waDgPvkk0+6yxTnQ4hj+xBX4nv55ZeTv6o8gtyJ/eEPf5imcdcO6ykuM3HixLSM3Km7/fbb07R071atf8uWLalOZsyY0Z2PLlcY7vAVl8dXHmSZb33rW6nM+noIg2gu+iwo4BwiCSJx2udBAdceIg0OBVw1FHAkkk+6wYHVGReOAq4XXJNgN998c7rrBZMuQ3muDSZvUL7wwgtJGOlrkghBHEuJgentwSBgxFatWtUzH+IKhm7M4t0zvY7333+/x4fjCoOQ1MuDvffeu7tuEXDYF5i+dpxzzjmd8847Lx0z2MaNG0vrw7mGu2z4v2iHH35432MNe++990r+KijgHCIJInHa50EB1x4iDQ4FXDUUcCSST7rB+cpXvpLWscsuu5SWLUIBVwYGUYY7XRIDgYJn33DnCXbWWWd1/fI8WxERgnfddVd3nbIuvS2YdQcO4CUA/RzcO++807MO/XwZwDLvvvtu+v/GG29Md87EsD7cEYOJgMO+yPJVLFu2rBtfZcU7fCtWrEiiUpteJ6zucCIUcA6RBJE47fOggGsPkQaHAq4aCjgSyaeqBgeNtjcuHAVcGTERPPD9/Oc/Tw/mo1saJs+b4c4Y/HoduPMEg5AprlMvB4PwOfLII7vLbLPNNqXlsB/r16/veTmguA6IPB0DQSZ34MTw4sDJJ5/c8wyeCDjsi9xFqwLdv7DHH388Pe+mWbhwYSkG+/+LX/yiu/2qLuR+2yxCAecQSRCJ0z4PCrj2EGlwKOCqoYAjkXyyGhwYugC1X6CAK1N8ceGDDz5IPgzzIIYBk2VZ3GGDXXzxxT3r+Oijj5Ifz5lhWkxvCyZvoaIRF9EIAYiyw7Q4e+6553rWJVZc5r777ku+fl248sybCDi8SQrTb6YWY+VlhOLQISKsMKxIcfniFyZwPYLpLzDAfvWrX/X4LCjgHCIJInHa50EB1x4iDQ4FXDUUcCSST1aDI+PCab9AAVemOJRGcZwyMTw/Jj4MmQHDXbSTTjop+eTlAJiO1duCFYcRueSSS5IPd8MwjbdHse4TTjihu0zxzmBx3QcccECaxjVSTK6VYvIc34YNG7q+J554IvlwVxGG7eFNZvgwxhxMujllGi8zyPbxggRMti+GMeBkmaeeeir5lixZ0vXhuMD0c38WFHAOkQSROO3zoIBrD5EGhwKuGgo4Esknq8HB+YAhHzDGmZ4HKOCqkTtNxbc/xfSyGLC2+HwZDHfNivUjpmNh8vamXhZDi2Barxtdo6effnrP8hCBRcMzdWeccUZ3GQiv4nogDDEgsZgsd9RRRyWxVjQRcwJe8Cga6gp1IPNxPmEIEW3PPPNMz3pwJxF3Kou+flDAOUQSROK0z4MCrj1EGhwKuGoo4Egkn/o1OP3GhaOAGx5w1w1Dj9xwww2do48+ujR/KEBEHn/88Wm8NNwd1PUOw0C++KrG8uXL0xuw+ksQsh50YcqdQrD77runZ+L0shgaBOvad999S/MA7jxiHDmMWSfP02kwhMqtt96aBB++3KDjYVdffXUpzoICziGSIBKnfR4UcO0h0uBQwFVDAUci+eQ1ODDcuUHDWfRTwA0+MAg47R/LyFu32t8PCjiHSIJInPZ5UMC1h0iDQwFXDQUcieST1+Dc+YMfpHVedtllPX4KuMEHNmgCDlb19m4/KOAcIgkicdrnQQHXHiINDgVcNRRwJJJPdRocDCui10sBN/ig63aHHXYo+ccy1qDE/RhXAg5Jmcv8+fNLvjoMJW7evHlscAYcaXD08e0HzlEcc+2vA84Z7fPAB7uB9ntgW9HzG/sY2WZ0e8yndhDJJzn22l/k4IMPTuv92te+1vWh4cfD7HpZD5zXkfN0KPkUiUM5kYd33nln2ndd12RwEAGnj3E/vJywqJNPVeB8i8TtvPPO6TzF/0nA4ZdVLngIctKkSSV/P7A84rTfA4MVIk4+BswGZ3CRBkcf437gHMVbVtrvgfMG54z2e2y77bbpNXnt98C2Iuc3wD7mbjOaT4D51A4i+YRjj4fUtV+DsblgeNAe09OnT08iTi/ngfM6cp5KPiGP9TyPSPuEciIP5Zuluq7J4CACTh/jfkTOGYmrk08atDOR9gnCTXQbu1BJo0S6fNiFWg27UEkkn3K6fGAP/PjH6X9pPPQyHuxCJU0zrrpQ9QJ1iCSIxGmfBwVce4g0OBRw1VDAkUg+5TQ4GFYEhpyggCODAgWcQyRBJE77PCjg2kOkwaGAq4YCjkTyKbfBeeihh9J3PSngyKBAAecQSRCJ0z4PCrj2EGlwKOCqoYAjkXyKNDiwlStXUsCRgYACziGSIBKnfR4UcO0h0uBQwFVDAUci+RRpcMQo4MggQAHnEEkQidM+Dwq49hBpcCjgqqGAI5F8ijQ4yD8YhhXR8zwo4EjTUMA5RBJE4rTPgwKuPUQaHAq4aijgSCSfog0OvkV57733lvweFHCkaSjgHCIJInHa50EB1x4iDQ4FXDUUcCSST9EGR8aFW7JkSWlePyjgSNNQwDlEEkTitM+DAq49RBocCrhqKOBIJJ+iDQ7eQn3rrbeyt0cBR5qGAs4hkiASp30eFHDtIdLgUMBVQwFHIvkUbXAg4M4777y0PeSInm9BAUeahgLOIZIgEqd9HhRw7SHS4FDAVUMBRyL5FG1wZBy4I444ovPxxx93pk2bVlqmCgo40jQUcA6RBJE47fOggGsPkQaHAq4aCjgSyadog1McyBd25ZVXlpapggKONM24EnDYeC4otBQ8h2iMwAZnsJEGRx/jfoiA036PoZyjTcYB7OPEiRNLfo/o9phP7SCST9HzFB/snjdvXvp/7Zo1tbcb3V7xuq/neURikH/Iw3Xr1qV903VNBgcRcPoY9yNyzkhcJDYaN2vWrHSe4v8k4IqJMtZhgzPYSIOjj2s/RMBpf5vAPuIOh/aPNMynwSaST1G22267zvz589P/e+65Z9ouGkq93KCC/KOAawci4PQxbgOzZ89O5yn+H8guVNrgmz7G/WAXajXD1YVKG3zTx7cfOPb49a79HvpbqOjKgXnDigxqFypt8E0f435EzlGJi+TTsHWh6gXqEEkQidM+j6KAw92CHJYuXdo58MADS34P/MLcfffdS36PvfbaK6H9dYjELVy4MO2j9ntg3yLbA4iL1g3ON/yvj3E/KOCqGQ4Bp4+RB47hHnvsUfJ7HHLIIZ1/+7d/K/k9ovmE+ozEDSUvkIeLFi0q+T2azqdog6MFHIA98OMfl5YtMmgCTtdzHXAs0GZovwdyKXLsFyxYEDpP8QJKpL0YjXyK5sWhhx6a2kX8r49xPyLnqMRF8mlcCjg9zwP7t/3225f8HqjYyIUDBzKyjyASt/XWW3cPZg4QKZHtgehFFXUTOWco4KoZDgGn/R6Iyy0nQMMPAaD9HtF8itYNzutIHMAx/MIXvlDyezSdT9EGp0rAnXLKKUnE9RtWZNAEnPbXAduLNMbYZr+6s5C60X4PXEcj+4i6jJwzQ8knxEXqBt38aBe132Mo5YzWTeScoYCrAQWcTfSiGm1wKOCqiYoUEM0nxOWWE1DA2TSdT9EGp0rAgYceeqhz7rnnlvwCBZwNBZwN4iJ1QwFXg0iCSJz2eVDA2VDA2VDA2UTzCXG55QQUcDZN51O0wbEEHIBddtllJT+ggLOhgLNBXKRuKOBqEEkQidM+Dwo4Gwo4Gwo4m2g+IS63nIACzqbpfIo2OJ6Asx4ap4CzoYCzQVykbijgahBJEInTPg8KOBsKOBsKOJtoPiEut5yAAs6m6XyKNjj9BBzyE7bvvvuW5lHA2VDA2SAuUjcUcDWIJIjEaZ8HBZwNBZwNBZxNNJ8Ql1tOQAFn03Q+RRucfgIOXHHFFZ077rij5KeAs6GAs0FcpG4o4GoQSRCJ0z4PCjgbCjgbCjibaD4hLrecgALOpul8ijY4noADMD2sCAWcDQWcDeIidUMBV4NIgkic9nlQwNlQwNlQwNlE8wlxueUEFHA2TedTtMGpI+A2b95cehaOAs6GAs4GcZG6oYCrQSRBJE77PCjgbCjgbCjgbKL5hLjccgIKOJum8yna4NQRcEAPK0IBZ0MBZ4O4SN1QwNUgkiASp30eFHA2FHA2FHA20XxCXG45AQWcTdP5FG1w6go4jPb/8ccfd6ZNm5amKeBsKOBsEBepm3En4HBwckGh0UBqv4ckVg5yEuCk1fM8RMBpvwcqFieP9ntIg6P9dYjETZgwIe2j9nvIRVX76yCJpf0eqJvIOSMCTvs9cN5EzhnUDdB+D7moan8dsI8457TfI7q9aD4hLlI3aPgnTZpU8ns0nU9yrdH+OoiA034PbA/b1X6PaDkRJ+Ivh/+/vfPxtayq7vg/QpwwzGNKxswPMjOAMM2Q1hAwxViGWAspoQRLJBIIaIBGiIpBoURSCKmASvlR5JcUmxk1YoWBVAE10hYSW0BKzBT5HVDCgPTW727X9bx17nrr7O8b9nvvvO9OPpl31z3rnn32uevsz5xz77nYf9iPPj4LtOuvv778zR5rugLnn8tg1of6Y46lgK2n1scaEzgfz8Bxm3nP2IkCHx8Ce6yBwGFe9PGMxfSTHRvmmA+fsX1YBA4daIEdjFuC7du8eXMvvtxgx2bdunVlG318TJjA+fiYwDauWbOmFx8L27Ztmxx66KG9+JjAPty4cWMvPhaw/7AffXwWd955Z5G422+/vffccgX1N/ZjqQmcj4+JI488ssyLPj4Edh5uCXzG9qEuoQboEmoM8tixYd4zJnA+nqFLqDFsPSGvtp9Al1BjWtcT1sdc8hl6CRWgXq3pEmqMLqHGII8Zm1V3CdUvMASmQCzPxzIkcDESuBgJXAxbT8ir7SeQwMW0rid2wqkROICJ5re//W35TBwzphK4GAlcjARuAEyBWJ6PZUjgYiRwMRK4GLaekFfbTyCBi2ldT+yEUytw4Iorrpjs3buXGlMJXIwELkYCNwCmQCzPxzIkcDESuBgJXAxbT8ir7SeQwMW0rid2wmEEDqD993//dy+eIYGLkcDFSOAGwBSI5flYhgQuRgIXI4GLYesJebX9BBK4mNb1xE44rMA9/PDDReJ8PEMCFyOBi5HADYApEMvzsQwJXIwELkYCF8PWE/Jq+wkkcDGt64mdcFiBw/vlO9/5zuS6667rPbcQErgYCVyMBG4ATIFYno9lSOBiJHAxErgYtp6QV9tPIIGLaV1P7ISzGIH72Mc+Vs7CHXPMMb3nIyRwMRK4GAncAJgCsTwfy5DAxUjgYiRwMWw9Ia+2n0ACF9O6ntgJZzECh3Va889HSOBiJHAxErgBMAVieT6WIYGLkcDFSOBi2HpCXm0/gQQupnU9sRPOYgXuK1/5igTOIYGLQR4zNhK4ATAFYnk+liGBi5HAxUjgYth6Ql5tP4EELqZ1PbETzmIFDn/jtiIPPvBAb5lZSOBiJHAxErgBMAVieT6WIYGLkcDFSOBi2HpCXm0/gQQupnU9sRPOgRA4vOfQLrjggt5yHglcjAQuRgI3AKZALM/HMiRwMRK4GAlcDFtPyKvtJ5DAxbSuJ3bCORACBx5+6KFBl1IlcDESuJhVJ3B4oVpscH08wwqyBpMNDJJ/LgPbhx+Y9vEMFAiKy8czbMLx8SEwefYDzD6eYbLh40NAHjs2zHvGBM7HM7Au5j2DsTGBr6E74dSCbWT6yq4Peeivj2fYROXjGVu3bp2sXbu2F8/A+hazjT6WYbLh40PAPtywYUMvnsHWE9tPdkyx/7AffTzDH2v+6q/+qghcNlZWT8wxg9k+1B9zLAVsPbHHGnaeMYHz8Qz2WLqYemKPNRA4zIs+nrGYfrJjw7xn4DO2D4vA4UVqsTdsLYvJY3KxfZs3b+7FM7BDgI9nsP20XB/LwEGV2Yd2APDxIdgb1scz2PWZwPn4EJh1svt+MWOKbcT/Gn08g10f+z5l9/22bdsmc3NzvXgG20/L9bEhsHnYhzjb7+MZ7PoWk8fkYv9hP/p4xqy6+OhHP1ok7thjj+0tb7D9tFwfy7CrGT4+BLYu2GMNOzYmcD4+BGZ9s/b9UNgxPeKII8q86OMZi+knk8vu+02bNk33oS6hBugSagzy2LFh3jMmcD6eoUuoMWw9Ia+2n0CXUGNa1xPWh1wfzzhQl1ANtFtvvbUXN/D+ZMcGebVjo0uoMbqEGsPWE8aGec/0LqH6BYbAFIjl+ViGBC5GAhcjgYth6wl5tf0EEriY1vXETjgHWuCy24pI4GIkcDESuAEwBWJ5PpYhgYuRwMVI4GLYekJebT+BBC6mdT2xE86BFjhMRL/97W8np59+eu85IIGLkcDFSOAGwBSI5flYhgQuRgIXI4GLYesJebX9BBK4mNb1xE44B1rgwEL3hZPAxUjgYiRwA2AKxPJ8LEMCFyOBi5HAxbD1hLzafgIJXEzremInnPdC4ADavn37enEJXIwELkYCNwCmQCzPxzIkcDESuBgJXAxbT8ir7SeQwMW0rid2wnmvBC66L5wELkYCFyOBGwBTIJbnYxkSuBgJXIwELoatJ+TV9hNI4GJa1xM74bxXAgd27949ue666+bFJHAxErgYCdwAmAKxPB/LkMDFSOBiJHAxbD0hr7afQAIX07qe2AnnvRS4P/3TPy1n4Y4++uhpTAIXI4GLkcANgCkQy/OxDAlcjAQuRgIXw9YT8mr7CSRwMa3riZ1w3kuBA9bssQQuRgIXI4EbAFMgludjGRK4GAlcjAQuhq0n5NX2E0jgYlrXEzvhvNcC5+8LJ4GLkcDFSOAGwBSI5flYhgQuRgIXI4GLYesJebX9BBK4mNb1xE4477XAge5tRSRwMRK4GAncAJgCsTwfy5DAxUjgYiRwMWw9Ia+2n0ACF9O6ntgJp4XAoV9oF1xwgQRuASRwMatO4HDQqWXjxo292BCYvA0bNpQ8iJh/LgPbhx+39fEMrAvr9fEM9JPZRsv1sQz7YVsfz8CbgFkfQB47Nj42BGzfzp07e/EM9JF5z2BsgI9nYF2L2UZmnez62HpCHtPPD3zgA5MtW7b04hmt68mONT4+BOxDTB4+ntG6ntgxxf7DfvTxjNpjzaOPPFIkzuqp1djYxOjjQ2DrqfWxBsfRxWyjj2Uspp7YY80xxxxT5kUfz1hMP5lcjA2277DDDqsCPoN9iL+LwAkhhBDLgcsuu6wI3K5du3rPCSF+jy6hBugSagx7WYO95IPt0yXUPuxlQsDWE/Jq+wl0CTWmdT2xl3xaXEI17LYif/RHf0SNDdZXOzZ2CfWOb3yjrFtt5Te/jxei9j3azWPq6YBdQvULDIEpEMvzsQwJXIwELkYCF8PWE/Jq+wkkcDGt64mdcFoKHEC7/fbbqbHB+mrHxgvcTTfdJFYwErgFYArE8nwsQwIXI4GLkcDFsPWEvNp+AglcTOt6Yiec1gJ34403lkn4wQcf7D2XgfXVjo0XOP+8WDmcfPLJ1fuQeY9aHlNPErgBSOBmI4GLkcDFIK+2n0ACF9O6ntgJp7XAYV3vvvtu9UQMsL7asZHAjQcJXAJTIJbnYxkSuBgJXIwELoatJ+TV9hNI4GJa1xM74bQWOLw/165dO3nhhRfKbUX88wuB9dWOjQRuPEjgEpgCsTwfy5DAxUjgYiRwMWw9Ia+2n0ACF9O6ntgJZykEDnkXX3zxZN++fVX3BENe7dhI4MaDBC6BKRDL87EMCVyMBC5GAhfD1hPyavsJJHAxreuJnXCWSuAwNmj79+/vLROBvNqxkcCNBwlcAlMgludjGRK4GAlcjAQuhq0n5NX2E0jgYlrXEzvhLKXA7d69u2pCRl7t2EjgxoMELoEpEMvzsQwJXIwELkYCF8PWE/Jq+wkkcDGt64mdcJZS4Oy+cEcffXRvuVkgr3ZsJHDjQQKXwBSI5flYhgQuRgIXI4GLYesJebX9BBK4mNb1xE44SylweIxjANqJJ57YW9aDvNqxkcCNBwlcAlMgludjGRK4GAlcjAQuhq0n5NX2E0jgYlrXEzvhLLXAAbQHHnigt6wHebVjI4EbDxK4BKZALM/HMiRwMRK4GAlcDFtPyKvtJ5DAxbSuJ3bCWQ4Cd8UVVwyamJFXOzYSuPEggUtgCsTyfCxDAhcjgYuRwMWw9YS82n4CCVxM63piJ5zlIHDo95D7wiGvdmwkcONhVQkcOjBWsH1btmzpxcfC3Nxc2UYfHxMmcD4+JrCNmCB9fCxs3759sn79+l58TGAfbty4sRcfC9h/2I8+vhSgXXnllb34YkD9YR/efffd1ZO/WF6YwPl9PAbgMzbnF4GDCdaCZJyp8PEM5PlYhp0tguX65zLsoOrjGfjfH/5H5uMZdsbAx4fA5K1Zs6Zso49n2NkiHx8C8tixYd4zJnA+noF1Me8ZjI2dga2he8agFmwj01d2fchDf308A3nM2GzdurXcVd/HM+yg5eNDYPLsbJGPDwH7cMOGDb14BltPbD/ZMcX+w3708Qz2WGP1NOuYgYb7wvm4wawP9Yd9eOedd0rgVjgmcH4fLwTznrE85tiNmmeOwfAZm/N1CTVAl1Bj7I3u4xnsJR8TOB/P0CXUGLaekFfbT6BLqDGt68kmHB/PWA6XUI3stiLIqx0bXUIdD6vqEqpfYAhMgViej2VI4GIkcDESuBi2npBX208ggYtpXU/shLOcBA7cfvvtk1tvvbUXB8irHRsJ3HiQwCUwBWJ5PpYhgYuRwMVI4GLYekJebT+BBC6mdT2xE85yEziANuu2IsirHRsJ3HiQwCUwBWJ5PpYhgYuRwMVI4GLYekJebT+BBC6mdT2xE85yFLh333135kSNvNqxkcCNBwlcAlMgludjGRK4GAlcjAQuhq0n5NX2E0jgYlrXEzvhLEeBw3bMuq0I8mrHpqXAvfrqq2Uds9pNN9204DbXYM3HW7Fjx47JtddeO3nppZcmzz777OTss8/uLfNeIIFLYArE8nwsQwIXI4GLkcDFsPWEvNp+AglcTOt6Yiec5Shw4MILL5zs27ev1K3FkFc7NstF4NCeeeaZXg6DNR9fDHgPoH3ta1/rPef5n//5n2kfrP3qV7/qLXegkcAlMAVieT6WIYGLkcDFSOBi2HpCXm0/gQQupnU9sRPOchU4gIbbithj5NWOzVIInI8Daz6+XDjiiCNK/2655Zbec1327t1blsMZRYvZJW/c/sovfyCRwCUwBWJ5PpYhgYuRwMVI4GLYekJebT+BBC6mdT2xE85yFrjdu3fPm7CRVzs2y1Xgrrrqqsmll146OeGEEybf//73i0DZc6eccsrkzjvumDz99NOT733ve73Xuvjiiws+fvPNN09+/OMfl5yoLvEN3yeffHLy6KOPTr70pS/Ny0V74oknSt9OPPHEXi545ZVXCt3YPffcU3JPO+203vIHEglcAlMgludjGRK4GAlcjAQuhq0n5NX2E0jgYlrXEzvhLGeBA7itCAQBfyOvdmyWq8ChdS9F/smf/EmJ/8d//Ed5/M477xTRwhlItP1vvRW+1lu/e64s87tlcZn29ddf7y1jgoYGAcProb344ovz+o44YldffXVvG7DPcGn7qKOOmhe3XNzw2uccSCRwCUyBWJ6PZUjgYiRwMRK4GLaekFfbTyCBi2ldT+yEs9wFbufOnWXSxhkh5NWOzVIL3EknnTS54447Srz7nLXHH398cvzxx5fY6aefXmJ4nUMPPbTEcLyz5nP9424Nmxza8cAuc0KC8BhjiS+KoEEeh15C7QKZu/fee/9v5ZP3dmyBBC6BKRDL87EMCVyMBC5GAhfD1hPyavsJJHAxreuJnXCWu8ABkw/k1Y7NUgjcrPbUU09NDjvssOmy1rr5OOvmYwCXUtHsDFc396yzzip/X3fddfNy8GsWaLhU6nO64LdnIceMwPnGvB9qkMAlMAVieT6WIYGLkcDFSOBi2HpCXm0/gQQupnU9sRPOShC4K664YioItWOzFAKHM24GPnN20UUX9Za1Zo/xm7Q+ZthZrjPOOKOX+5WvfKX8DfnDJdQuaJA/y8FZOf/aBiNwAFL59ttvl1x8ds4/fyBZVQKHDrTADsYtwfZt3ry5F19usGOzbt26so0+PiZM4Hx8TGAb8c0sHx8L27ZtK5d6fHxMYB/ih6Z9fCxg/2E/+vhyAnKDz2VBhPxzGag/7MO77767evKvZdYl1Ahr9hhnwXzMwD3X0D7xiU/0cvGFhYXac889N8157bXXeq9tsAIHrO/4/J5/7kBiAuf3cQY7Dy8GrLMG+Azep/i7CBz+p1ILVowzHD6egTwfy7D/FeN/ZP65DDsD5+MZMGOcifHxDHsD+PgQmLz3ve99ZRt9PMP+V+zjQ0AeOzbMe8YEzscz8L5h3jMYG+DjGXbGwDEslAcAACzxSURBVMeHgG3Ee87HM9j1sfWEPGZscObm4IMP7sUzWteTHWt8fAh2Bs7HM7A+rNfHM9h+Ig/j6uMZ2H/Yjz6ewR5rumfg/HMZaJdffnkvvhCov3IG7v8/h+al4ECyGIED9rk1vyzusYaG46zPPffcc8vf119//bwcjDNiu3btmub4M3C4zIrL0zhLOETgsBzamWee2XsOX6R48803e/EDiQmc38cLwbxHLY+pJ8yhzDEfPmNzvi6hBugSaowdVH08w97kPp5hAufjGbqEGsPWE/Jq+wl0CTWmdT3ZhOPjGSvhEqqBBlHw8YVYikuoPj4La90YzjKiHXvssQsu2318+OGHl7/feOONeTm33XZbieNWJT7HwOfj0CBkQwTuvPPOK8s88sgj8+K4tIv2n//5n72cA8mquoTqFxgCOs0ePHwsQwIXI4GLkcDFsPWEvNp+AglcTOt6YieclSRwH/vYx8oEjjNH/rmIlSRw4Oc///n0Obs9CBru7xbl2i1B0H7zm99Mv/TRXeZv/uZvprHu7UvOOeec6TKQQGt79uzp9Q1ccskl02Xss2/W/LIHGglcAjrNHjx8LEMCFyOBi5HAxbD1hLzafgIJXEzremInnJUkcMjr3hduCC0F7uWXX+5dpoyIpKd72xBr/uetrNljfI6xK35o+OybvxkvPkPXbf6Sp33WDu273/1ur2+GFzcII75M4Zc70EjgEtBp9uDhYxkSuBgJXIwELoatJ+TV9hNI4GJa1xM74aw0gcPYoD3wwAO952fRUuBaYc3Hx44ELsEKxMczmEGSwMVI4GIkcDFsPSGvtp9AAhfTup7YCWclCpxdIsSNb/0ynrEJ3Pr16yVwM56LYN6jlsfUkwRuABK42UjgYiRwMcir7SeQwMW0rid2wlmJAofttF8R8Mt4xiRwf/u3f1u2AZdpP/WpT/WeHzsSuAQrEB/PYAZJAhcjgYuRwMWw9YS82n4CCVxM63piJ5yVKHD4Gz/jhJa9zpgEbsuWLeWboEytjgEJXEK3QGpgBkkCFyOBi5HAxbD1hLzafgIJXEzremInnJUqcODjH/94+abmH/zBH/SWNcYkcKsdCVyCL5ChMIMkgYuRwMVI4GLYekJebT+BBC6mdT2xE85KFjiA5m9i20UCNx4kcAmzCmQIzCBJ4GIkcDESuBi2npBX208ggYtpXU/shLPSBQ63FVloUpfAjQcJXMKsAhkCM0gSuBgJXIwELoatJ+TV9hNI4GJa1xM74ax0gdu5c2eZ1P09zwwJ3HhYVQKHN3ot6DQmSB/PsMKqwQ6qKGj/XIYJnI9nYGAxkft4hk04Pj4EJk+/hRqD9w3znsHYAB/PsAnHx4eAbcR7zscz2PWx9YQ8Zmww8bf8LVT7T5+PZ9ixxseHYALn4xlYH9br4xmLOQab/NWwkn4LNVrfxo0by8T+l3/5l73nUH9F4A7Ab6HiZrXd1/j2nj3lMRp+JxQxNPx2Kf7GZ/TQzj///N5riXpW1W+hogNjBduHb+T4+FiYm5sr2+jjY8IEzsfHBLYRZzh8fCxs37693JfKx8cE9iEEwcfHAvYf9qOPrzTQ9u7d24uj/rAP77777rKMl4Ia7P5z9th+kuqdd96ZfPnLXy4xtJUgcNZ8fDljAuf38RiAz9icr0uoAbqEGoM8dmyY94wJnI9n6BJqDFtPyKvtJ9Al1JjW9YT1MZd8VvolVCO6rYhdQr3/e99blLDYpdoLLrhgGrPmlzUkcAeWVXUJ1S8whIUKZCGYQZLAxUjgYiRwMWw9Ia+2n0ACF9O6ntgJZywCBx5+6KHJ5ZdfPi9mAvfSSy9VT/5dHn/88cn+/fvL8Qd9v+iii6YSdPHFF0+OPvroshz+PuWUU8rfkcCddtpp5cfpv/c7qYzqB6//9NNPl/Weeuqp0zj+vuqqq8qE311+w4YNJQ7JwWOM1d/93d9Nnn322cmPfvSjIqC27F//9V9P+46c7ucHP/jBD06uueaayQ9/+MPJF77whXJmqLueXbt2TT73uc+Vv7/0pS+V/tlr42zu5z//+bJteI2jjjpqXu5ikcAlZAUSwQySBC5GAhcjgYth6wl5tf0EEriY1vXETjhjEjiA1r2tCPr593//94sSuLPPPrvk2q8frFmzZvLiiy/+nwH9ruHvSy65pDyHFl1CRZ61Z555ZvL6669PH3fXZ+2nP/3p5Iknnpi3zBFHHFH+xvZ0c2z7IFH4CI61Rx55pKzLGpbt/vA9+n711VeX+JNPPlliuFT83HPPTS8RQ9JsPQ8//PA097XXXpuu1xpyLQ+t28fFIoFLGFIgs2AGSQIXI4GLkcDFsPWEvNp+AglcTOt6YiecMQpcd5K/8sory+PFCNyDDz5Ycg899NB5cb8ui0UCt3v37vIYn9Wz5U12rG7XrVtXHkO6bJnf/OY3JRatF/uvm4OzgGg333xzmOMfn3XWWeUx+m5n9zZv3jxdN868IWYCh37718LZPsgjtuUXv/hFia1du3a63GKRwCUMKZBZMIMkgYuRwMVI4GLYekJebT+BBC6mdT2xE87YBM7fF87aYgQOZ6Nm5VrzsVkChzNjkB5/5uzGG28sy3z2s58tj3GJFO273/3udJkvfvGLk3379k1r1Jo9D1HrvsY999xTHn/yk5+cLoPLtXiNbj+7r/HKK6+Ux/jCTrd/xx13XInjMiwem8Dde++9vdfCZVyL4fIr2plnnjnv9RaDBC5hSIHMghkkCVyMBC5GAhfD1hPyavsJJHAxreuJnXDGJnAAt/v41n33lc9oWVuMwO1/662ZudZ8bJbA2S1I8I1VfJauCxo+7+ZfFw3S9/Wvf32eWD311FPlOZwhm9UPzB/dhnVCArvHBmv+se+b9Q+XRrGcCVx337/99tvzXguce+65JXbZZZfNiy8GCVzC0ALxMIMkgYuRwMVI4GLYekJebT+BBC6mdT2xE84YBQ5zQ9T8skPwtw8xZr0m2iyBwxmwhRrO8tlr4DNpb7zxhl9k+rxdIsXZu6gfuEedyZc1iFzU96zZJVMIXPfyKZDA/R4J3AAkcLORwMVI4GKQV9tPIIGLaV1P7ISz0gWue5ZtSPOvOQR8WH9W7qzXRJslcCY0/ndbMR6I2WfM8A1VfG6vuwy+zIB2ww03TGOPPfZYiZ1wwgnl33/+53+ePodLqfjiRfc1TAjxLVPrJ5o97x93wXo//elPl79rBQ6XUv3rsUjgEmYVyBCYQZLAxUjgYiRwMWw9Ia+2n0ACF9O6ntgJZ6ULHKiROJ87hEcffXRm7qzXRJslcIcffnj5GyLVXf62224r8UsvvbQ8/ta3vlUed2/Bceyxx5bYLbfcMo1B9NBeffXV8u/xxx8/fQ7rx2Xf7npwSxG0D3/4w9N+otnz9mUFf9sQkybcVgSPJXALI4EbgARuNhK4GAlcDPJq+wkkcDGt64mdcMYgcMYQkfM5Q7Cf6sJn0brxWa+JNkvg8Ni+YYoGYbJLs2j+NdDwxYLoViPd5b761a/Oi+PLBNZeeOGF6Wf40GyZ7iXaPXv2lJh9tg7trU7ON7/5zWkeK3C4Px/aT37yk3nL1SCBS8gKJIIZJAlcjAQuRgIXw9YT8mr7CSRwMa3riZ1wxiRwIGt++aFAeLpfNACzXhPt+eefL3+fccYZ5fE555wzfb57DzY0fPateyNd0L1vm7V/+7d/6/XJGm7d4Z/79a9/3cn+v8+wdb85eu21106fs2+84tjqG0Sz+7q4BcoQgbN759lNf/FZODTc5Le7XA0SuIQhBTILZpAkcDESuBgJXAxbT8ir7SeQwMW0rid2whmbwBlR88sNBetGu+uuu3rPLRWL3abW4Ezhn/3Zn/XiQ5HAJdQUiM/zsQwJXIwELkYCF8PWE/Jq+wkkcDGt64mdcMYqcGDWJVW/TA1o3W9yLhUYO9xCBO3ll1/uPb8cwa9YoDH73VhVAieEEEKsdvBTWtb8xFmD/aD9YiTkQGDt+9//fu+5MWMC5/fv2CgCh/9V1bJ9+/ZebAiLydu2bVsvnoHtw48H+3gG1rV169ZePAN57DYy24d1MfsQ28b2E3ns2PjYELB9+HaVjw+BWSe2jd0+dkyxjcw62fWx9cTu+x07dpTfZvTxjMWMKbN9i6kL7MMPfOADvXgGO6bM9gF232P/YT/6eAY7povZ90we+ol9aM1LQS3+R+SXApxZ/MxnPtOLjx0TOL+PF4KpCcDWE95vTB58xuZ8XUIN0CXUGPayBnvJB9unS6h92MuEgK0n5NX2E+Bgo0uos2ldT+wlnzFfQgXoJ/bhHd/4xgEROLF0rKpLqH6BITAFYnk+liGBi5HAxUjgYth6Ql5tP4EELqZ1PbETjgROrBQkcAlMgViej2VI4GIkcDESuBi2npBX208ggYtpXU/shCOBEysFCVwCUyCW52MZErgYCVyMBC6GrSfk1fYTSOBiWtcTO+FI4MRKQQKXwBSI5flYhgQuRgIXI4GLYesJebX9BBK4mNb1xE44EjjRBb/Das0/t9RI4BKYArE8H8uQwMVI4GIkcDFsPSGvtp9AAhfTup7YCUcCJ7p8+ctflsD9fx5TTxK4AUjgZiOBi5HAxSCvtp9AAhfTup7YCUcCt7SceeaZk+985zuTJ598cvKDH/wg/PH3j3zkI5MHH3yw/KYoHn/oQx8q96XrLvPBD35wcs0115Qfnsfr+B+m37Vr1+TCCy8sf0PUHnvssfIvbiWDGOYd/NSVtauuuqr8Dqzvy1IhgUtgCsTyfCxDAhcjgYuRwMWw9YS82n4CCVxM63piJxwJ3NLR/XH7bjvllFPmLfejH/1o3vM/+9nPJi+++GL515bBcXFW674OfogeP1J/6aWXzlvm3XffLc/jeOzbJz/5yV6/lwoJXAJTIJbnYxkSuBgJXIwELoatJ+TV9hNI4GJa1xM74Ujglo5nn3229OnNN9+cPPXUU5P9+/eXxxCqbj1aww/U48flrXUFDmfw0JD73HPPlR+cR3v88ceny0DgrGGd+/btmz7G/sDPc0HwrEESTzrppF6/lwoJXAJTIJbnYxkSuBgJXIwELoatJ+TV9hNI4GJa1xM74UjgloYTTjihSNZ55503L37++eeXftovLTz//PPl8fHHHz9d5sYbbywxE7hXXnmlPPaXO4877rgSxxk8PDaB+/aePdNlcMkVDb/ugMf6DNzv85h6ksANQAI3GwlcjAQuBnm1/QQSuJjW9cROOBK45cHc3Fy5dGrCZgL3zjvvTF566aV5y2IM0UzgrPnXtOdw1g5/m8DZZ97ARz/60RKDFOKxBO73eUw9SeAGIIGbjQQuRgIXg7zafgIJXEzremInHAnc0oB+PfHEE1NZQoOsdQUOX0pAu/fee3v5kDIvcFHDmT4sB4Gzvw2MDdpXv/rV8lgC9/s8pp4OmMDhDVILOo2V+3iGTQA12MSIQfLPZWD7Nm3a1ItnYF3s9jHbaLk+lnHwwQdPJ/8a7ODo40Noue+BCZyPZ6CPzHsGYwN8PMNkw8eHgG086KCDevEMdn1sPSGPGRv8cDM+iO3jGa3ryY41Pj4E7EMcXH08o3U9sWOK/Yf96OMZ7LHG6qnV2KD+sA/vuuuu6sn/veS+++4r/dn/1luT3bt3l/cY4qeeemqJQ+DsSw7333//vNzoDBy+ZToLXK7FcmMROL+PF4J5z1gek8vOT/AZm/OLwOGMQy3WYR9fCCyPPB/P6Aqcfy7DBM7HM0zgfDzDdqaPZ7BjYwLn4xl2UPXxIdhB1cczmPcMMIHz8QwrEB/PMIHz8QybcHx8CNjG2lz2PQPYekIeMzYmcD6e0bqe7Fjj40MwgfPxjNb1xI6pCZyPZ7DHmq7A+ecymLFBDvbhnXfeuayk5O233+71B2dv7IsFdgn15ZdfLo937NgxXc7O0pnA2Rcb/G1DTHhwWxE8HovA+X28EMx7xvKY9zc7P+Hzizbn6xJqAAaXOXVvBx0fHwKTp0uoMbqEGsPWkx3kfDxDl1BjWtcT1odcH8/QJdSl4Ve/+lXpz9VXX12OafjCwS9/+cupPH3xi18sy5177rnlMc7UYfvPOOOM6TImcBdffHF5jC8z2L788z//85KDZt8kHSJwl1xyyfT1mWPCe8mquoTqFxgCUyCW52MZErgYCVyMBC6GrSfk1fYTSOBiWtcTO+FI4JYOu4xqDbf8WLNmzfSxLYezYiZjEDAIGc7gQchsmVn3gbMvLxh79+7tCRyOwWg33HDDNIZ+WNN94PrPLYQEbgASuNlI4GIkcDHIq+0nkMDFtK4ndsKRwC0t+MWEm2++eV7d4uzZBRdc0FsW22HHPzT/5YbDDjus3JbkjjvuKP9iWf8aQ8F7Al+iWMxrHGgkcAlMgViej2VI4GIkcDESuBi2npBX208ggYtpXU/shCOBW97gCwxo119//TSGm/WiMeO/kpHAJTAFYnk+liGBi5HAxUjgYth6Ql5tP4EELqZ1PbETjgRueYPfPLX29NNPz/slBr/s2JHAJTAFYnk+liGBi5HAxUjgYth6Ql5tP4EELqZ1PbETjgRu+YNjHi6J4mycfenBL7MakMAlMAVieT6WIYGLkcDFSOBi2HpCXm0/gQQupnU9sROOBE6sFCRwCUyBWJ6PZUjgYiRwMRK4GLaekFfbTyCBi2ldT+yEI4ETKwUJXAJTIJbnYxkSuBgJXIwELoatJ+TV9hNI4GJa1xM74UjgxEpBApfAFIjl+ViGBC5GAhcjgYth6wl5tf0EEriY1vXETjgSuKUFP2B/1FFH9eJjBvv+lltu6cUzJHAJTIFYno9lSOBiJHAxErgYtp6QV9tPIIGLaV1P7IQjgVta0B577LFefOygff7zn+/FF0ICl8AUiOX5WIYELkYCFyOBi2HrCXm1/QQSuJjW9cROOBK4pWW1Cpz9lJiPL8SqEjgUSi02AdSymDwmF9u3efPmXjwDOwT4eAbbT8v1sYxDDjmkbKOPZ9jE6ONDsDesj2ew6zOB8/EhMOvk9z0/pthGyLiPZ7DrY9+n7L7ftm3bZG5urhfPYPtpuT42BDbP/rPo4xns+haTx+Ri/2E/+ngGe6xh+2m5PpZh/xm+6667qif/FqxWgbvooovKttf8J94Ezu/jhWDeM5bH5LLzzKZNm6ZzfhE468AYwfZt2bKlFx8LOKiuhn2I4vXxMYFtxBkOHx8L27dvn6xfv74XHxPYhxs3buzFxwL2H/ajj48F1B/24d13350K3LHHHju56qqrJkcfffQ0hjP+iOEH4y22Y8eOEsNx2mI4lt14442T//qv/5r8y7/8SxHH7mtffvnlJQdnaK699trJTTfdVOKzBA7LAXt8+OGHT+68887JM888M/nBD34wb70AfUPfITj/+I//OPn5z38++Yu/+It5yxjf/OY3y2+d4ndU7QfsPccdd9zk1ltvnTz77LOTRx99dObZUvzM1g9/+MPyOpiL/fMAkoabD2N9p5566rznMK779+8vY+XzIkzg/D4eAxhDm/N1CTVAl1BjkMeODfOeMYHz8QxdQo1h6wl5tf0EuoQa07qesD7mko8uoc5/ffzYOy7vWewf/uEfSl4395VXXpn32Bpyf/rTn07eeOONacwvYw1iY3ETOIghpAYNAoUYfhcVDa/9yCOPTC89vvPOOzNf+/nnn5+89tpr08e2DF4PDT/D9cQTT8z7RQesY9ZrYbn9b71V/n7xxRd7yzz33HOTF154YfrYnv/FL34xjWE88Dp+GfDZz362xE477bR58YhVdQnVLzAEpkAsz8cyJHAxErgYCVwMW0/Iq+0nkMDFtK4ndsKRwM3nl7/8ZZElqwechfLy0X2Ms2FoEKOPfOQjM5fpPoZ4XXrppeU4ZnEI3M6dO6fy1j0z9tBDD5XYkNdet27dNIZtQLN55KWXXiqP8dEjWwY/eo+Gs3t4fOihh05fC7KEGMbcGh6fddZZ5e+u5JoM7tq1a15/cMbQL2OPAaQF7dt79syLR0jgEpgCsTwfy5DAxUjgYiRwMWw9Ia+2n0ACF9O6ntgJRwI3HxyT0O65554iTWjf+ta3yr92WRTNzoA99dRTRZZ83X39618vy1122WXTHDS/PjRIo7Wbb7553vO4RIn25ptvzpMv/xo469eNYb+i4XKqXx4cf/zx09fGv4hhW9BwOba77Be+8IXJlVdeWfYZ2pNPPtl7PcgnJA1/d9sZZ5yx4L5Ge/3113vxWUjgEpgCsTwfy5DAxUjgYiRwMWw9Ia+2n0ACF9O6ntgJRwLXBw1ShXuVoUFo0M4555zp8/hcF/6GOOGSqn8NXBZEu++++6Y5aH4537wcoe/dBpH7xCc+0XsNuyTbBVKFy6n2GPMKLoVCPrvNBA4iBRn1r+P7gmXw2l3QcBYSy+Fzet2G5SG0+Cypf020t99+uxefhQQugSkQy/OxDAlcjAQuRgIXw9YT8mr7CSRwMa3riZ1wJHB9rEFILOdf//VfJy+//HL5MgKaXa6EUCHuXwNnntDw4/Pd1/TLoUFwPv7xj0+XWbt2bW85bMeePXvKuqx1X8OEsgvEys7AWcOXBj796U/Pu4RrAodtsbNos/jQhz5Ulv/xj39cLpd6TjjhhF4Otv/f//3fp+vHa3SfR1tonV0kcAlMgViej2VI4GIkcDESuBi2npBX208ggYtpXU/shLNaBO6f/umfBk/+9vkxa4jhEiIaPpCPD+7bsvggP0TP151ddj3zzDPL4+5rdUGDEOFvSCIavqyAx3jN66+/vlzunNW/7mu8+uqr85bB5Va03bt3h+vH5+7QTOCwLXhtX9M4Y2fbiDbrsuznPve5Iob4+4Ybbijj1X0eX2ZAw3PdOFr3CxILAUn025DBvEctj6knVuDgMxK4BAlcDHtQZSccCdxsWEkBbD0hr7afQAIX07qe2AlHAtcH0mSte5sLa12hOuyww0oM4vOpT32qxNasWTNd1uf6daF1byNyzTXXlBjOhuExvnyA1z7//POny3TPDHZf+6STTiqPcYy0ZscDa/Y5vvvvv38a+8lPflJiOKuIhvVdeOGFJYZblKDZZ/7scfeysX1T1dZvrXtZ92c/+1mJnX766dMY9gua/9xfhAQugSkQy/OxDAlcjAQuRgIXw9YT8mr7CSRwMa3riZ1wJHB98Nuk1j7zmc9M49b88t3261//evp398P51mbl+vvAdZftXlrFNz9N3ux5v3483z2DaMtYrHx+7f+Fa8hrWbPP/3WXeet3r2Off0Oz5+1WJ2gQPYyDXwbg8iqa/9JEhAQugSkQy/OxDAlcjAQuRgIXw9YT8mr7CSRwMa3riZ1wJHAHBpx1wxcXbrvttsnZZ5/de34x4PYe5513XrndBs4O+nFH27t3b7kpM+6thi8M+BsJ2+vgixl2phD88R//8fTSZxfczBevdeKJJ/aeAzjziNuQ4JYn9nk6z4c//OHJvffeW77Rixv/+ny0r33ta728CAlcAlMgludjGRK4GAlcjAQuhq0n5NX2E0jgYlrXEzvhSOBWPiZwPr6csXvQ1RyvJHAJTIFYno9lSOBiJHAxErgYtp6QV9tPIIGLaV1P7IQjgVv5rESBQ5v17d2FkMAlMAVieT6WIYGLkcDFSOBi2HpCXm0/gQQupnU9sROOBG7ls1IFrvvrEkNYVQKHDowVbB++Ju3jYwHfBloN+xAC5+NjAtuIz8b4+FjYtm1b+VyNj48J7MMx/5g99h/2o4+PBdQf9iHuoVY7+YvlhQmc38djAD5jc/6qELgtW7b04mMBv6+3GvbhahA4nOHw8bGwffv28sFpHx8TYxc47D/sRx8fC6g/Cdw4GLPAwWfmCZzf+CEgufYUteX5WIYuocboEmqMLqHGsPWEvNp+Al1CjWldT1gfc8lHl1DFSmFVXUL1CwyBKRDL87EMCVyMBC5GAhfD1hPyavsJJHAxreuJnXAkcGKlIIFLYArE8nwsQwIXI4GLkcDFsPWEvNp+AglcTOt6YiccCZxYKUjgEpgCsTwfy5DAxUjgYiRwMWw9Ia+2n0ACF9O6ntgJRwInVgoSuASmQCzPxzIkcDESuBgJXAxbT8ir7SeQwMW0rid2wpHAiZWCBC6BKRDL87EMCVyMBC5GAhfD1hPyavsJJHAxreuJnXAkcGKlIIFLYArE8nwsQwIXI4GLkcDFsPWEvNp+AglcTOt6YiccCZxYKUjgEpgCsTwfy5DAxUjgYiRwMWw9Ia+2n0ACF9O6ntgJRwInVgonS+AWhikQy/OxDAlcjAQuRgIXw9YT8mr7CSRwMa3riZ1wJHBipSCBS2AKxPJ8LEMCFyOBi5HAxbD1hLzafgIJXEzremInHAmcWCmcfPLJ1fuQeY9aHlNPErgBSOBmI4GLkcDFIK+2n0ACF9O6ntgJRwInVgoSuASmQCzPxzIkcDESuBgJXAxbT8ir7SeQwMW0rid2wpHAiZXCqhI4vHFrQTGjwHx8IdBZ5Pl4BtaDvPe973295zKwfZs2berFMyBG2Ck+noE+MtuIsVmzZk0vnrF27drp5F8D3nRMPwHymLHB9mE7fTzDBM7HM9BH5j2DsTnooIN68Qy8Z9gxxTbWrpOtJ4A89NfHM5BX20+wdevWybp163rxDLxnmG1k6wnvGWZ9APvw/e9/fy+e0bqesD5mbLD/sB99PAPvF2ZMrZ6YsUFe7dign9iHu3fvrp78xfLCBM7v44VYTD0x8wze18wxGD5jc34RuGOOOaaaHTt29GJDWEwek2uTv4+/V7D9tFwfy0DOStqHPjYEbF/rbWRh19d6+8r7dEY8g13fzp07J3/4h3/Yi2e0rqfF5LHHGnZ9i8ljcrH/sB99fAjM+vD+ZPJKLpmHffjggw+WyX9ubk6sUEzg/P5dCPY9w9YTC44xNl/oEmqALqHGsJc12Es+NjH6eIYuocaw9YS82n4CXUKNaV1PWB9zyQf7bzVdQlVb+c3v44Vg3qOWx9TTAbuE6hcYAlMgludjGRK4GAlcjAQuhq0n5NX2E0jgYlrXEzvhrBaB8/EhYH3MZIx14njj4xk2Nj6eYWdvfDwDY8m8ZxZTT8hjxmb79u1lXvTxjMX0kx0b5j0jgRuABC6GPaiyE44EbjaspAC2npBX208ggYtpXU/shCOBi8H6mMlYAheDPGZsJHADYArE8nwsQwIXI4GLkcDFsPWEvNp+AglcTOt6YiccCVwM1sdMxhK4GOQxYyOBGwBTIJbnYxkSuBgJXIwELoatJ+TV9hNI4GJa1xM74UjgYrA+ZjKWwMUgjxkbCdwAmAKxPB/LkMDFSOBiJHAxbD0hr7afQAIX07qe2AlHAheD9TGTsQQuBnnM2EjgBsAUiOX5WIYELkYCFyOBi2HrCXm1/QQSuJjW9cROOBK4GKyPmYwlcDHIY8ZGAjcApkAsz8cyJHAxErgYCVwMW0/Iq+0nkMDFtK4ndsKRwMVgfcxkLIGLQR4zNhK4ATAFYnk+liGBi5HAxUjgYth6Ql5tP4EELqZ1PbETjgQuButjJmMJXAzymLGRwA2AKRDL87EMCVyMBC5GAhfD1hPyavsJJHAxreuJnXAkcDFYHzMZS+BikMeMjQRuAEyBWJ6PZUjgYiRwMRK4GLaekFfbTyCBi2ldT+yEI4GLwfqYyVgCF4M8ZmwkcANgCsTyfCxDAhcjgYuRwMWw9YS82n4CCVxM63piJxwJXAzWx0zGErgY5DFjs+oEDi9Uiw2uj2dYQdZgsoFB8s9lYPs2btzYi2egQFBcPp5hE46PD4HJw0GV2YcmGz4+BOSxY8O8Z0zgfDwDfWTeMxgbE/gauhNOLdhGpq/s+th6sonKxzO2bt06OeSQQ3rxDKxvMdvoYxkmGz4+BOzDDRs29OIZbD2x/WTHFPsP+9HHM9hjjR1LW40N1sccSwHWh/r38Qz2WMPOMyZwPp6B4zZzvFhMPbHHGggc5kUfz1hMP9mxYd4z8Bnbh0XgrKDHCLZvy5YtvfhYmJubK9vo42PCBM7HxwS2EQcdHx8LOKiuX7++Fx8T9p9FHx8L2H/Yjz4+Fuw/wz4+JkzgfHxMHHnkkWVe9PGxAJ+xfahLqAG6hBqDPHZsmPeMCZyPZ+gSagxbT8ir7SfQJdSY1vWE9TGXfHQJNQbrYy6H6RJqDPKYsVl1l1D9AkNgCsTyfCxDAhcjgYuRwMWw9YS82n4CCVxM63piJxwJXAzWx0zGErgY5DFjI4EbAFMgludjGRK4GAlcjAQuhq0n5NX2E0jgYlrXEzvhSOBisD5mMpbAxSCPGRsJ3ACYArE8H8uQwMVI4GIkcDFsPSGvtp9AAhfTup7YCUcCF4P1MZOxBC4GeczYSOAGwBSI5flYhgQuRgIXI4GLYesJebX9BBK4mNb1xE44ErgYrI+ZjCVwMchjxkYCNwCmQCzPxzIkcDESuBgJXAxbT8ir7SeQwMW0rid2wpHAxWB9zGQsgYtBHjM2ErgBMAVieT6WIYGLkcDFSOBi2HpCXm0/gQQupnU9sROOBC4G62MmYwlcDPKYsZHADYApEMvzsQwJXIwELkYCF8PWE/Jq+wkkcDGt64mdcCRwMVgfMxlL4GKQx4yNBG4ATIFYno9lSOBiJHAxErgYtp6QV9tPIIGLaV1P7IQjgYvB+pjJWAIXgzxmbCRwA2AKxPJ8LEMCFyOBi5HAxbD1hLzafgIJXEzremInHAlcDNbHTMYSuBjkMWMjgRsAUyCW52MZErgYCVyMBC6GrSfk1fYTSOBiWtcTO+FI4GKwPmYylsDFII8ZGwncAJgCsTwfy5DAxUjgYiRwMWw9Ia+2n0ACF9O6ntgJRwIXg/Uxk7EELgZ5zNisOoHDm6gWe8P6eIZNADXYxIhB8s9lYPs2bdrUi2dgXez2MdtouT6WcfDBB08n/xrsAODjQ1jMvmfyTOB8PAPrYt4zGBvg4xkmGz4+BGzjQQcd1ItnsOtj6wl5zNhs3bp1sm7dul48o3U92bHGx4eAffj+97+/F89g64LtJzum2H/Yjz6ewR5rrJ5ajQ3qjzmWAraeWh9rTOB8PIOtCzYPsMeaI444osyLPp6xmH4yuez8BJ+xfVgEzjowRrB9W7Zs6cXHwtzcXNlGHx8TJnA+PiawjTjD4eNjAf8rXr9+fS8+JrAPN27c2IuPBew/7EcfHwuov7EfS03gfHxMHHnkkWVe9PGxAJ+xfVgEDqcpa0EyDNDHM5DnYxlYD/Jgq/65DGwfjNXHM+wMnI9n2CD7+BCYPDsD5+MZ9r9iHx8C8tixYd4zJnA+nmH/w/HxDPtfsY9n2P+KfXwIVpA+vhBWFz4+BLaekMeMDc7cHHLIIb14BltP7NjYGQMfHwL2Ic7A+XhG63pixxT7D/vRxzPYY033DJx/LoMZG+Qwx1LLZeqp9bHGBM7HM5ainpDHjI2dgfPxjMX0k8ll5yc7A4e/9Rm4AAwu89kLKywfHwKTp8/AxegzcDFsPSGvtp9An4GLaV1PWB9yfTxDn4GLwfpQ/z6eYZLp4xk2Nj6eoc/AxSymn+zYMO+Z3mfg/AJDYArE8nwsQwIXI4GLkcDFsPWEvNp+AglcTOt6YiccCVwM1sdMxhK4GOQxYyOBGwBTIJbnYxkSuBgJXIwELoatJ+TV9hNI4GJa1xM74UjgYrA+ZjKWwMUgjxkbCdwAmAKxPB/LkMDFSOBiJHAxbD0hr7afQAIX07qe2AlHAheD9TGTsQQuBnnM2EjgBsAUiOX5WIYELkYCFyOBi2HrCXm1/QQSuJjW9cROOBK4GKyPmYwlcDHIY8ZGAjcApkAsz8cyJHAxErgYCVwMW0/Iq+0nkMDFtK4ndsKRwMVgfcxkLIGLQR4zNhK4ATAFYnk+liGBi5HAxUjgYth6Ql5tP4EELqZ1PbETjgQuButjJmMJXAzymLGRwA2AKRDL87EMCVyMBC5GAhfD1hPyavsJJHAxreuJnXAkcDFYHzMZS+BikMeMjQRuAEyBWJ6PZUjgYiRwMRK4GLaekFfbTyCBi2ldT+yEI4GLwfqYyVgCF4M8ZmwkcANgCsTyfCxDAhcjgYuRwMWw9YS82n4CCVxM63piJxwJXAzWx0zGErgY5DFjI4EbAFMgludjGRK4GAlcjAQuhq0n5NX2E0jgYlrXEzvhSOBisD5mMpbAxSCPGRsJ3ACYArE8H8uQwMVI4GIkcDFsPSGvtp9AAhfTup7YCUcCF4P1MZOxBC4GeczYrDqBQwfGCrZvy5YtvfhYmJubK9vo42PCBM7HxwS2EROkj48FHFTXr1/fi48J7MONGzf24mMB+w/70cfHAupv7MdSEzgfHxNHHnlkmRd9fCzAZ2wfFoHDmYpakAw79vEM5PlYhp0tguX65zLsoOrjGfgfDv535OMZdsbAxzPsfyo+nrFmzZqyjT6eYf8r9vEhII8dG2ynj2eYwPl4Bt43zHsG/ysCPp5h/yv28SFgG2v7yr5nAPLQXx/PQB4zNjhzs3bt2l48ww5aPp7Bjo0da3x8CNiHGzZs6MUzFnMsZeqJHVPsP+xHH8+wM9M+nmH11GpsUH/MsRSw9cQea9h5xgTOxzMwlrXHJ7AU8wz+k4F50cczmPeM5bFjw7xn4DO2D3UJNUCXUGPsje7jGewlHxM4H8/A+4Z5z+gSaowdVH08Q5dQY1rXk004Pp6hS6gxWB9zOUyXUGOQx4zNqruE6hcYAlMgludjGRK4GAlcjAQuhq0n5NX2E0jgYlrXEzvhSOBisD5mMpbAxSCPGRsJ3ACYArE8H8uQwMVI4GIkcDFsPSGvtp9AAhfTup7YCUcCF4P1MZOxBC4GeczYSOAGwBSI5flYhgQuRgIXI4GLYesJebX9BBK4mNb1xE44ErgYrI+ZjCVwMchjxkYCNwCmQCzPxzIkcDESuBgJXAxbT8ir7SeQwMW0rid2wpHAxWB9zGQsgYtBHjM2ErgBMAVieT6WIYGLkcDFSOBi2HpCXm0/gQQupnU9sROOBC4G62MmYwlcDPKYsZHADYApEMvzsQwJXIwELkYCF8PWE/Jq+wkkcDGt64mdcCRwMVgfMxlL4GKQx4yNBG4ATIFYno9lSOBiJHAxErgYtp6QV9tPIIGLaV1P7IQjgYvB+pjJWAIXgzxmbCRwA2AKxPJ8LEMCFyOBi5HAxbD1hLzafgIJXEzremInHAlcDNbHTMYSuBjkMWMjgRsAUyCW52MZErgYCVyMBC6GrSfk1fYTSOBiWtcTO+FI4GKwPmYylsDFII8ZGwncAJgCsTwfy5DAxUjgYiRwMWw9Ia+2n0ACF9O6ntgJRwIXg/Uxk7EELgZ5zNhI4AbAFIjl+ViGBC5GAhcjgYth6wl5tf0EEriY1vXETjgSuBisj5mMJXAxyGPGZjUJ3P8Cc/EQbh6qPF4AAAAASUVORK5CYII=>