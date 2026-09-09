import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATABASE_NAME = os.path.join(DATA_DIR, "notebook.db")

os.makedirs(DATA_DIR, exist_ok=True)

notebooks = [
    (1, 1001, 1, "ASD Lecture Notes — Agentic Systems", "2026-07-28"),
    (2, 1001, 3, "Database Fundamentals Notebook", "2026-07-30"),
    (3, 1002, 2, "Programming 2 — OOP & GUI", "2026-08-01"),
    (4, 1002, 9, "Cybersecurity Basics Notes", "2026-08-03"),
    (5, 1003, 10, "Data Science Intro Notebook", "2026-08-05"),
    (6, 1003, 7, "Environmental Science Notes", "2026-08-07"),
    (7, 1004, 4, "Japanese Fundamentals Notebook", "2026-08-10"),
    (8, 1004, 5, "Philosophy Theory Notes", "2026-08-12"),
    (9, 1005, 6, "Modern Art Notebook", "2026-08-15"),
    (10, 1005, 8, "Digital Marketing Notes", "2026-08-18"),
]


notes = [
    (1, 1, "Intro to Microservices with Docker",
     "Docker packages an application together with its dependencies into a single "
     "container image, so it runs the same way on a laptop, a CI runner, or a "
     "production server. Each of our five student features ships as its own set of "
     "containers rather than one shared process, which is what makes independent "
     "deployment and independent failure possible.\n\n"
     "A docker-compose file describes how several containers should run together: "
     "which image to build, which ports to expose, and which environment variables "
     "to inject. In this project each student's services get their own compose "
     "service block, joined later into one shared file so the whole system can be "
     "started with a single command.\n\n"
     "The key discipline is keeping each container's responsibility narrow. A "
     "database container should only serve data over HTTP or hold a SQLite file; it "
     "should never contain business logic or prompt-handling code that belongs to a "
     "backend container instead.",
     "2026-07-29"),
    (2, 1, "Understanding Agentic AI Loops",
     "An agentic system does not just answer a question in one shot — it decides "
     "how to approach a task, takes an action, checks whether that action produced a "
     "sensible result, and adjusts if it did not. The common name for this cycle is "
     "Plan, Act, Observe, Adapt.\n\n"
     "Plan means choosing a strategy before doing any work: for summarising a short "
     "note, the right strategy might be to skip the language model entirely and "
     "return the text unchanged, since there is nothing meaningful left to compress. "
     "Act means carrying out that strategy, which might mean calling a language "
     "model with a carefully assembled prompt.\n\n"
     "Observe means checking the result against simple, mechanical criteria — is "
     "it empty, is it just an echo of the input, is it actually shorter. Adapt means "
     "reacting to a failed observation: retrying with a stricter prompt, falling "
     "back to a deterministic algorithm, or truncating the output. Making each "
     "stage's reasoning visible in a trace object is what turns a black-box AI call "
     "into something a marker or teammate can actually audit.",
     "2026-07-29"),
    (3, 1, "Flask REST API Design Patterns",
     "A thin route in Flask should do exactly three things: read the incoming "
     "parameters or JSON body, call a single service function to do the real work, "
     "and format whatever that function returns into a response. Nothing else "
     "belongs in a route handler.\n\n"
     "Keeping routes thin means SQL queries, HTTP calls to other services, and "
     "prompt assembly all move into dedicated service modules. If the team later "
     "decides responses should be HTML fragments instead of JSON, only the last "
     "line of each route needs to change — the service functions underneath do "
     "not care how their return value gets rendered.\n\n"
     "This project uses one service module per external dependency: one file talks "
     "to the database service over HTTP, one file talks to the language model, one "
     "file reads prompt text from disk. Each of those files is the only place in "
     "the codebase allowed to perform that particular kind of I/O, which keeps "
     "changes contained to a single file no matter which dependency changes shape.",
     "2026-07-30"),
    (4, 2, "SQL Joins and Normalization",
     "Normalization is the process of structuring a relational database so that "
     "each piece of information is stored in exactly one place. A notebook's title "
     "lives in the notebooks table; a note's content lives in the notes table; "
     "nothing about a notebook is duplicated inside every one of its notes.\n\n"
     "A join is how you recombine normalized tables when you need related "
     "information together in a single query. To answer 'which course does this "
     "note belong to', the notes table does not store a course_id directly — "
     "instead the query joins notes to notebooks on notebook_id, and reads "
     "course_id from the notebooks side.\n\n"
     "Getting normalization right early avoids painful bugs: if course_id were "
     "duplicated onto every note row, renaming or reassigning a notebook's course "
     "would require updating every note individually instead of a single row, and "
     "the two copies could quietly drift out of sync.",
     "2026-07-31"),
    (5, 2, "Indexing Strategies for SQLite",
     "An index lets SQLite find matching rows without scanning every row in a "
     "table, in the same way a book's index lets a reader skip straight to a page "
     "instead of reading cover to cover. Without an index, a search query against "
     "thousands of notes would get noticeably slower as the table grows.\n\n"
     "SQLite creates an index automatically on a PRIMARY KEY column, but a column "
     "that is searched often and is not the primary key — like notebook_id on "
     "the notes table, since every note lookup by notebook filters on it — "
     "benefits from an explicit index.\n\n"
     "Running a SQLite-backed service inside a Docker container does not change "
     "any of this: the database file lives inside the container's filesystem "
     "exactly as it would on a bare machine, and the same indexing rules apply "
     "whether the process happens to be containerized or not.",
     "2026-07-31"),
    (6, 2, "Transactions and ACID Properties",
     "ACID stands for Atomicity, Consistency, Isolation, and Durability — the "
     "four guarantees a database transaction is supposed to provide. Atomicity "
     "means a multi-step change either fully happens or does not happen at all; "
     "there is no state where a notebook was deleted but its notes were left "
     "behind.\n\n"
     "SQLite wraps every write in an implicit transaction unless told otherwise, "
     "which is why deleting a notebook and cascading that delete to its notes can "
     "be expressed as a single operation with foreign key constraints, rather than "
     "two separate steps that could fail halfway through.\n\n"
     "Consistency means the database never ends up violating its own rules, like a "
     "note pointing at a notebook_id that does not exist. Isolation and Durability "
     "matter more under concurrent access and after a crash respectively — less "
     "visible day to day, but they are why a database is trusted with data that a "
     "plain file is not.",
     "2026-08-01"),
    (7, 3, "Object-Oriented Design Principles",
     "Encapsulation means an object controls access to its own internal state "
     "instead of exposing raw data for any other code to modify directly. A "
     "Notebook class, for example, would expose a method to rename itself rather "
     "than letting external code overwrite its title field freely.\n\n"
     "Inheritance lets a more specific class reuse behavior from a more general "
     "one, but it is easy to overuse: this project's own instructions explicitly "
     "avoid inheritance hierarchies and abstract base classes for a small course "
     "project, favoring plain functions and modules that are simple to read end to "
     "end.\n\n"
     "The real value of object-oriented principles here is not building deep "
     "class hierarchies but choosing clear boundaries of responsibility — the "
     "same idea that shows up as 'one file per external dependency' in a "
     "service-oriented backend, just applied at the level of objects instead of "
     "modules.",
     "2026-08-02"),
    (8, 3, "Building GUIs with Event-Driven Programming",
     "A graphical interface spends most of its time waiting for something to "
     "happen — a click, a key press, a network response arriving — rather "
     "than running through a fixed sequence of steps top to bottom. That "
     "waiting-then-reacting model is called event-driven programming.\n\n"
     "A callback is the piece of code that runs when a particular event fires. In "
     "a browser, clicking a 'Summarise' button on a note does not run any code "
     "until that click event happens; only then does the registered callback fire "
     "and start the HTTP request to the backend.\n\n"
     "The htmx library used in this project's frontend embraces the same idea "
     "declaratively: instead of writing a callback in JavaScript for every button, "
     "an HTML attribute like hx-post declares which event should trigger which "
     "request, and a small amount of JavaScript is reserved for handling the "
     "response afterward.",
     "2026-08-02"),
    (9, 3, "Unit Testing OOP Code",
     "A unit test exercises one function or method in isolation, without needing "
     "its real collaborators to be running. Testing a route that calls a language "
     "model would normally require a real model server to be available — "
     "mocking replaces that dependency with a fake that returns a controlled, "
     "predictable value instead.\n\n"
     "Mocking has to target the name as it is looked up, not where it is "
     "originally defined: if a function is imported into another module, patching "
     "the original definition does not affect the already-bound name inside the "
     "importing module. Getting this wrong is one of the most common mistakes when "
     "testing Python code with mocks.\n\n"
     "Pytest fixtures make this pattern reusable — a fixture can patch a whole "
     "set of dependencies once and hand back a ready-to-use test client, so each "
     "individual test only needs to describe the specific input and expected "
     "output it cares about.",
     "2026-08-03"),
    (10, 4, "Common Web Vulnerabilities",
     "SQL injection happens when untrusted input is concatenated directly into a "
     "SQL query string instead of being passed as a parameter, letting an attacker "
     "smuggle in extra SQL that the application never intended to run. Using "
     "parameterized queries everywhere — never building SQL with string "
     "formatting — closes this off completely rather than trying to sanitize "
     "input by hand.\n\n"
     "Cross-site scripting, or XSS, happens when untrusted input is rendered into "
     "a page as raw HTML instead of being escaped first, letting an attacker's "
     "script run in another user's browser. A JSON-only API reduces this risk "
     "somewhat since the frontend controls how data gets inserted into the DOM, "
     "but the frontend rendering code still has to escape user-supplied text "
     "rather than trusting it.\n\n"
     "Both vulnerabilities share the same root cause: treating untrusted input as "
     "if it were trusted code or trusted markup, instead of always treating it as "
     "inert data.",
     "2026-08-04"),
    (11, 4, "Container Security Basics",
     "A Docker image should be built from a minimal base — python:3.11-slim "
     "rather than a full desktop distribution — so there is less software "
     "inside the container that could carry a vulnerability. Every package that is "
     "not actually needed at runtime is extra attack surface for no benefit.\n\n"
     "Secrets like API keys should never be baked into an image layer; a value "
     "written into a Dockerfile with COPY or ENV becomes part of the image itself "
     "and can be extracted by anyone who can pull it. Environment variables "
     "injected at container start time, or a gitignored .env file mounted in for "
     "local development, keep secrets out of the built artifact.\n\n"
     "A .dockerignore file matters for security too, not just image size — "
     "without one, an entire local .env file or test directory could accidentally "
     "get copied into a build context and end up baked into the final image.",
     "2026-08-04"),
    (12, 5, "SQL for Data Analysis",
     "A well-written SQL query can do the same aggregation work as several lines "
     "of application code, and doing it in the database avoids pulling every row "
     "across the network just to filter or summarize it in Python afterward. GROUP "
     "BY combined with COUNT or AVG is the most common pattern for turning raw "
     "rows into a summary.\n\n"
     "For a search feature, a LIKE query with wildcards is a simple way to match a "
     "keyword against text columns, though it does not understand word boundaries "
     "or relevance the way a dedicated search engine would — a query for 'sql' "
     "will also match 'mysql' or 'nosql' unless the surrounding logic accounts for "
     "that.\n\n"
     "Filtering by an additional column, like course_id, alongside a text match is "
     "done by combining conditions with AND in the WHERE clause — the two "
     "filters narrow the result set independently of each other.",
     "2026-08-06"),
    (13, 5, "Intro to Agentic Data Pipelines",
     "A data pipeline moves and transforms data through a sequence of stages — "
     "extract, clean, aggregate, load — and an agentic pipeline adds a "
     "decision-making layer on top that chooses which stage to run next based on "
     "what it observes about the data so far, rather than always following the "
     "same fixed sequence.\n\n"
     "Automation without any observation step is brittle: a pipeline that blindly "
     "proceeds to the next stage regardless of whether the previous stage actually "
     "succeeded will happily process garbage data all the way through. Checking a "
     "stage's output against a sanity condition before continuing is the same "
     "Observe idea used in the note-summarisation feature, just applied to data "
     "engineering instead of language model calls.\n\n"
     "Keeping each pipeline stage as a small, separately testable function makes "
     "it possible to verify the Observe checks in isolation, without needing a "
     "full pipeline run every time a check is adjusted.",
     "2026-08-06"),
    (14, 5, "Data Visualization Fundamentals",
     "A chart's job is to make a pattern in the data easier to see than it would "
     "be in a raw table — a bar chart for comparing categories, a line chart "
     "for showing a value change over time. Picking the wrong chart type for the "
     "data can hide the pattern instead of revealing it.\n\n"
     "Color should carry meaning, not just decoration: using a consistent color "
     "for the same category across multiple charts helps a reader build a mental "
     "model faster, while random or purely aesthetic color choices force the "
     "reader to keep re-reading the legend.\n\n"
     "For accessibility, a color-only encoding excludes readers with color vision "
     "deficiency — pairing color with a second cue, like a pattern or a direct "
     "label, keeps the chart legible for everyone reading it, not just readers "
     "with typical color vision.",
     "2026-08-07"),
    (15, 6, "Climate Change Fundamentals",
     "Greenhouse gases trap heat in the atmosphere that would otherwise radiate "
     "back out to space, and rising concentrations of carbon dioxide and methane "
     "since industrialization are the primary driver of the warming trend measured "
     "over the last century. The effect is well understood physically, even "
     "though predicting exact regional outcomes is harder.\n\n"
     "Emissions from burning fossil fuels for energy and transport make up the "
     "largest share of human-caused greenhouse gas output, followed by "
     "agriculture and land-use change. Reducing emissions in the energy sector "
     "specifically has the largest single lever for slowing the overall warming "
     "trend.\n\n"
     "Feedback loops can accelerate or dampen warming — melting ice reduces "
     "the reflective surface that once bounced sunlight back to space, which in "
     "turn increases how much heat the earth absorbs, an example of a "
     "self-reinforcing feedback loop rather than a simple linear response.",
     "2026-08-08"),
    (16, 6, "Renewable Energy Systems",
     "Solar panels convert sunlight directly into electricity through the "
     "photovoltaic effect, while wind turbines convert the kinetic energy of "
     "moving air into electricity through a spinning generator — both are "
     "intermittent sources, producing power only when the sun is out or the wind "
     "is blowing, unlike a fossil fuel plant that can run continuously on "
     "demand.\n\n"
     "Grid-scale battery storage is what makes intermittent renewable sources "
     "more practical for continuous supply, storing excess energy generated "
     "during peak sun or wind and releasing it later when generation drops. "
     "Without storage, a grid relying heavily on renewables needs a "
     "fast-responding backup source to cover the gaps.\n\n"
     "Energy density matters when comparing sources: a wind farm needs far more "
     "land area to generate the same power output as a natural gas plant, which "
     "is one of the practical siting challenges renewable projects have to work "
     "around.",
     "2026-08-08"),
    (17, 7, "Hiragana and Katakana Basics",
     "Hiragana is one of the two phonetic syllabaries used in written Japanese, "
     "made up of 46 basic characters that each represent a syllable rather than a "
     "single consonant or vowel sound the way English letters do. It is typically "
     "the first writing system Japanese learners study, used for native Japanese "
     "words and grammatical particles.\n\n"
     "Katakana covers the same 46 sounds as hiragana but with a visually distinct "
     "character set, used mainly for loanwords borrowed from other languages, "
     "foreign names, and for emphasis in a way similar to italics in English.\n\n"
     "Both syllabaries are learned before kanji, the third writing system, "
     "because kanji characters are frequently given furigana — small hiragana "
     "characters written alongside them — to indicate pronunciation for a "
     "reader who has not yet learned that particular kanji.",
     "2026-08-11"),
    (18, 7, "Basic Japanese Grammar Structures",
     "Japanese sentence order is subject-object-verb rather than English's "
     "subject-verb-object, so a sentence like 'I eat sushi' becomes literally 'I "
     "sushi eat' when translated word for word. The verb consistently comes last "
     "in a standard sentence, which takes deliberate practice for a native "
     "English speaker to internalize.\n\n"
     "Particles are short grammatical markers attached after a word to show its "
     "role in the sentence — wa marks the topic, wo marks the direct object, "
     "ni often marks a destination or time. Unlike English prepositions, which "
     "come before the noun they modify, Japanese particles come after.\n\n"
     "Because particles carry the grammatical relationships that English relies "
     "on word order for, Japanese word order is comparatively flexible as long as "
     "the particles attached to each word are correct.",
     "2026-08-11"),
    (19, 8, "Introduction to Epistemology",
     "Epistemology is the branch of philosophy concerned with the nature of "
     "knowledge itself — what it means to know something, and how a belief "
     "earns the status of knowledge rather than remaining mere opinion. The "
     "classical definition treats knowledge as justified true belief: the belief "
     "must be true, the person must believe it, and they must have adequate "
     "justification for it.\n\n"
     "Justification is the part most philosophical debate centers on, since it "
     "is possible to hold a true belief for the wrong reasons, which intuitively "
     "should not count as genuine knowledge. Gettier's famous counterexamples "
     "showed that justified true belief can still fail to feel like real "
     "knowledge in certain edge cases.\n\n"
     "Separating knowledge from mere true belief matters practically too: a "
     "lucky guess and a well-reasoned conclusion might both turn out correct, but "
     "only one of them was arrived at in a way worth trusting again next time.",
     "2026-08-13"),
    (20, 8, "Ethics: Utilitarianism vs Deontology",
     "Utilitarianism judges an action by its consequences: an action is right if "
     "it produces the greatest overall good for the greatest number of people, "
     "regardless of the intent behind it or any rule it might break along the "
     "way. This makes utilitarianism a consequentialist theory.\n\n"
     "Deontology instead judges an action by whether it follows a moral rule or "
     "duty, independent of the outcome it produces — lying is wrong under a "
     "deontological view even if a particular lie happens to produce a better "
     "outcome than telling the truth would have.\n\n"
     "The two frameworks can disagree sharply on hard cases: a utilitarian might "
     "endorse sacrificing one person to save five, while a strict deontologist "
     "would reject that trade because it treats the one person purely as a means "
     "to an end rather than respecting a rule against harming them directly.",
     "2026-08-13"),
    (21, 9, "Cubism and Abstract Expressionism",
     "Cubism, pioneered by Picasso and Braque in the early twentieth century, "
     "broke from single-viewpoint perspective by depicting a subject from "
     "multiple angles simultaneously within one flattened composition, "
     "fragmenting form into geometric facets rather than rendering it "
     "realistically from a fixed vantage point.\n\n"
     "Abstract expressionism emerged decades later in postwar New York and moved "
     "even further from representational subject matter, emphasizing "
     "spontaneous, gestural mark-making and large-scale canvases meant to convey "
     "emotion directly through the physical act of painting rather than through "
     "recognizable imagery.\n\n"
     "Despite the gap in time and style between the two movements, both share a "
     "rejection of the idea that a painting's job is to accurately depict the "
     "visible world — cubism reassembles it into geometry, abstract "
     "expressionism abandons depiction almost entirely in favor of gesture and "
     "color.",
     "2026-08-16"),
    (22, 9, "Modern Art Movements Timeline",
     "Impressionism in the late nineteenth century broke from academic painting "
     "by capturing fleeting light and color with visible brushstrokes rather than "
     "smooth, precise detail, and is generally treated as the starting point of "
     "the modern art era covered in this notebook.\n\n"
     "Cubism followed in the early twentieth century, then surrealism explored "
     "dream logic and the unconscious mind through unsettling, dreamlike imagery "
     "in the interwar period, and abstract expressionism arrived after the second "
     "world war as painting moved further from representing recognizable "
     "subjects at all.\n\n"
     "Tracking movements as a sequence can be misleading, since many overlapped "
     "in time and artists often moved between styles across a career rather than "
     "belonging to a single movement permanently — the labels are more "
     "useful as a study aid than as a strict historical boundary.",
     "2026-08-16"),
    (23, 10, "SEO and Content Marketing Strategies",
     "Search engine optimization is the practice of shaping a page's content and "
     "structure so that search engines can understand what it is about and rank "
     "it appropriately for relevant queries, rather than trying to trick the "
     "ranking algorithm directly.\n\n"
     "Keyword research identifies the actual terms an audience searches for, "
     "which then guides both the content itself and metadata like page titles "
     "and headings — writing content nobody searches for, no matter how "
     "well-optimized the technical structure is, will not generate meaningful "
     "traffic.\n\n"
     "Content marketing pairs with SEO by producing material genuinely useful to "
     "the target audience, which earns organic backlinks and repeat visits over "
     "time, in contrast to paid advertising which stops generating traffic the "
     "moment the budget stops.",
     "2026-08-19"),
    (24, 10, "Social Media Analytics Basics",
     "Engagement rate measures how much an audience actively interacts with a "
     "post — likes, comments, shares — relative to how many people saw "
     "it, and is generally a more meaningful metric than raw follower count for "
     "judging whether content is actually resonating with an audience.\n\n"
     "Analytics dashboards track these metrics over time, letting a marketer "
     "compare which content formats or posting times produce a higher engagement "
     "rate, then adjust the content strategy based on what the data actually "
     "shows rather than on assumption.\n\n"
     "Vanity metrics like follower count can grow while genuine engagement or "
     "business impact stays flat, which is why serious social media analytics "
     "work focuses on conversion and engagement rate rather than headline "
     "audience size alone.",
     "2026-08-24"),
]


def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notebooks (
            notebook_id     INTEGER PRIMARY KEY,
            student_id      INTEGER NOT NULL,
            course_id       INTEGER NOT NULL,
            notebook_title  TEXT NOT NULL,
            created_date    TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            note_id       INTEGER PRIMARY KEY,
            notebook_id   INTEGER NOT NULL,
            note_title    TEXT NOT NULL,
            note_content  TEXT NOT NULL,
            updated_date  TEXT NOT NULL,
            FOREIGN KEY (notebook_id) REFERENCES notebooks (notebook_id) ON DELETE CASCADE
        )
    """)

    conn.execute("DELETE FROM notes")
    conn.execute("DELETE FROM notebooks")

    conn.executemany(
        "INSERT INTO notebooks (notebook_id, student_id, course_id, notebook_title, created_date) "
        "VALUES (?, ?, ?, ?, ?)",
        notebooks,
    )
    conn.executemany(
        "INSERT INTO notes (note_id, notebook_id, note_title, note_content, updated_date) "
        "VALUES (?, ?, ?, ?, ?)",
        notes,
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
