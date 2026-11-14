# Agent execution and workspace controls: verification

November 14, 2026. Implementation reference: [contract](agent-execution-contract.md).

## Actual checks

- Rebuilt API, project-runtime and scientific-worker Docker images. Worker capabilities
  advertise Python, JavaScript and shell from the installed image label.
- Retrieved actual arXiv paper 2010.11315. Python plotted paragraph counts from its
  extracted JSON into a PNG; JavaScript saved real section counts as a JSON dataset.
  Both isolated analysis runs succeeded and retained input/code/output provenance.
  No fabricated observations or synthetic scientific inputs were used.
- The first bounded provider request exposed LangChain's reserved `runtime` tool argument
  collision. Renamed the tool argument to `language`, keeping the backend payload field
  `runtime`. A provider-free LangGraph ToolNode invocation verified the mapping.
- The same real agent request produced a pending tag request. Isolated WebKit verified
  compact controls below the composer, hover descriptions, Off blocking approval, and
  Ask approval persisting the tag on the actual retrieved material.
- Clear-chat API retries with the same idempotency key return the same generation.
  Sources and experiments remain. Clearing during the real active agent run returned
  CHAT_BUSY.
- Python compilation, frontend TypeScript and scoped ESLint checks passed.

## Boundaries and remaining coverage

Scripts execute as complete saved programs in temporary network-disabled workers.
This uses explicit LangChain tools and the existing controller, not a native interactive
SandboxBackend. There is no arbitrary dependency installation. Shell is advertised from
its installed interpreter; the real scientific checks exercised Python and JavaScript.
No paid agent retry/cancellation stress suite was run. Revision-bound publication and
execution refuse concurrent plan changes; code artifacts cannot count as data evidence.

The user authorized deletion of 36 archived test containers. They were removed with
volumes preserved, and startup reconciliation now selects active projects only so removed
archived containers stay removed. After the final API restart, only the six active project
containers and the frontend/API were running and healthy. No idle shutdown was added.

## Final integration results

- A second bounded provider request saved actual JavaScript code and applied an Allow
  tag operation. Its execution exposed a Flask-context dependency in the background
  controller. The controller now receives its manager explicitly. Without another paid
  request, the same agent-generated script succeeded through the background tool path:
  **22 extracted sections and 93 paragraphs**, saved as document-counts.json.
- API checks confirmed ordinary experiment PATCH preserves its implementation, stale
  implementation saves return 412, and a new decision on an already applied request
  returns 409.
- Isolated WebKit confirmed the literature dialog opens at 1200 × 968 in a 1500 × 1000
  viewport and closes correctly; no page errors were observed.
- A separate production frontend Docker image built successfully without disturbing
  the development container. There were exactly two live provider requests for this
  feature; no additional model call was made for the background-controller repair.

The final corrected automatic model-to-execution sequence was not repeated as another
paid provider request. Its publication, LangChain tool dispatch and actual background
worker execution were verified separately using the real generated code and data.

Isolated WebKit also confirmed Clear chat removes displayed history and draft text,
survives a page reload, and preserves the real source and experiment. No page errors
were observed during the controls, literature or clear-chat checks.

## Script discoverability follow-up

Studio now exposes attached/missing implementation status on every experiment tab,
including actual filename/runtime and a View script link. An explicit action prepares
a chat request to generate or revise code on the selected experiment, without creating
a replacement or executing it. Isolated WebKit verified both states against the existing
hand-gesture plans and checked the exact experiment/artifact targets. No model request
was sent. Agent instructions now distinguish a saved plan from confirmed attached code.

## Generic experiment upload follow-up

Added Upload data file to the experiment header, opening and focusing the existing
file import flow. JSON datasets/documents now use the existing strict validator.
Isolated WebKit uploaded the real document-counts.json dataset, declared its generated
origin and attached it to the paper-structure experiment. The saved implementation was
preserved and no page errors or model requests occurred.

## Materials upload correction

Moved the generic upload action from the experiment header into Materials. Uploads
are project-scoped and do not require or change an experiment. Materials now defaults
to the raw All materials list; curated views remain optional. The actual JSON dataset
uploaded through the new dialog appears in the catalog without an experiment association.
TypeScript and scoped ESLint passed; isolated WebKit verified the raw default, visible
uploaded file and removal of the misplaced experiment button. No model calls were made.
