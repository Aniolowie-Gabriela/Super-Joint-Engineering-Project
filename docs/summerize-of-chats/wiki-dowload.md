# Conversation Summary – EU4 AI Expert Project

## 1. Project Goal

The goal is to create a **local AI assistant specializing in Europa Universalis IV** that answers players' questions about game mechanics, strategies, and individual nations.

The system will use an **LLM + RAG architecture**, allowing the language model to access information stored in a local knowledge base.

Example questions:

- What is the best way to start an Ottoman campaign in 1444?
- What unique mechanics does the Ottoman Empire have?
- Which missions are worth completing early in the game?
- How does the Ottoman Decadence mechanic work?
- Which expansion strategies are the most effective?

At this stage, **we are not planning to integrate the application with a running game or read data from the current campaign**.

---

## 2. Selected Architecture

| Component | Technology |
|---|---|
| Language model | Qwen3 8B or 14B |
| LLM runtime | Ollama |
| Backend | Python |
| Vector database | ChromaDB |
| Embeddings | EmbeddingGemma |
| Architecture | RAG |
| User interface | Streamlit |
| Main knowledge source | Europa Universalis IV Wiki |

All major components are intended to run locally, without requiring paid APIs to generate answers.

### System Flow

```text
User
  │
  ▼
Streamlit Interface
  │
  ▼
Python Backend
  │
  ├── EmbeddingGemma
  │        │
  │        ▼
  │     ChromaDB
  │        │
  │        ▼
  │   Retrieved Information
  │
  ▼
Ollama + Qwen3
  │
  ▼
Answer to the User
```

---

## 3. Gathering Data for RAG

Initially, we considered collecting questions and answers from Reddit, particularly from `r/eu4`.

We discussed using Python and the PRAW library to retrieve posts and comments.

However, we concluded that **the EU4 Wiki would be a better primary knowledge source**.

### Why the Wiki?

- Information is organized by topic.
- It contains descriptions of mechanics, missions, events, and national ideas.
- Retrieved information is easier to classify automatically.
- There is no need to convert discussions into question–answer pairs.
- The content can be processed directly into RAG documents.

**Important conclusion:** RAG does not require data in a question–answer format. We can use excerpts from Wiki articles.

Reddit remains a potential supplementary source of player strategies and experiences.

---

## 4. Methods for Downloading Data from the EU4 Wiki

We considered four options:

| Method | Description | Assessment |
|---|---|---|
| MediaWiki API | Programmatically retrieving articles | Preferred |
| XML export | Exporting multiple articles | Very good |
| HTML scraping | Downloading and parsing HTML | Alternative |
| Manual copying | Collecting information by hand | For testing only |

### Preferred Approach

**Python + MediaWiki API**, provided that access to the EU4 Wiki API is available.

Target workflow:

```text
EU4 Wiki
    │
    ▼
Download Articles
    │
    ▼
Save Original Data (RAW)
    │
    ▼
Clean Text
    │
    ▼
Split into Logical Chunks
    │
    ▼
Assign Metadata
    │
    ▼
Save Data (PROCESSED)
    │
    ▼
EmbeddingGemma
    │
    ▼
ChromaDB
```

We agreed that keeping the original downloaded files is worthwhile so articles do not need to be downloaded again if processing errors occur.

**We have not yet tested how well the individual methods work on actual EU4 Wiki articles.**

---

## 5. First Nation – The Ottoman Empire

We decided that the **Ottomans (`TUR`)** will be the first nation for which we prepare a knowledge base.

Earlier project assumptions called for starting with Poland, but we changed this choice during the conversation.

### Information Categories

| Category | Content |
|---|---|
| `starting_position` | The Ottoman situation in 1444 |
| `national_ideas` | National ideas, traditions, and ambitions |
| `missions` | Mission tree, requirements, and rewards |
| `events` | Unique events |
| `government` | Government reforms, mechanics, and Decadence |
| `strategy` | Opening strategies and expansion |

### First Phase

Initially, we will limit data collection to three categories:

1. `starting_position`
2. `national_ideas`
3. `missions`

This will allow us to test the entire process on a small information set.

---

## 6. Organizing Data in ChromaDB

We decided to use **a single collection**, for example:

`eu4_nations`

Each knowledge chunk will have metadata that enables information filtering.

### Example Structure

```json
{
  "country_tag": "TUR",
  "category": "missions",
  "topic": "constantinople",
  "source": "eu4_wiki",
  "source_file": "ottomans_missions.xml",
  "verified": true,
  "content_type": "fact"
}
```

This is an example format, not an actual record downloaded from the Wiki.

### Meaning of Metadata Fields

| Field | Meaning |
|---|---|
| `country_tag` | Nation identifier |
| `category` | Information category |
| `topic` | Specific topic |
| `source` | Source of the information |
| `source_file` | Local source file |
| `verified` | Whether the information has been verified |
| `content_type` | Fact or strategy |

We also agreed that:

- We do not need a separate collection for each nation.
- Each knowledge chunk can have its own metadata.
- Retrieval will combine semantic similarity with metadata filtering.
- Information about game mechanics should be kept separate from subjective strategies.

### Is `source_url` Necessary?

It is not required.

Because the data will be stored locally, we can use `source_file` instead of `source_url`.

However, the original URL can be useful for checking whether information is still up to date.

---

## 7. Application Interface

We agreed that it would be useful to create **a single local web interface in Streamlit** with two main modules.

### Module A – EU4 AI Expert

The primary user interface.

Features:

- Chatting with a local LLM.
- Selecting a nation.
- Asking questions about EU4.
- Enabling and disabling RAG.
- Displaying the sources used to generate an answer.
- Conversation history.
- Ability to change the language model.

The interface should resemble a conventional chatbot, such as ChatGPT.

### Module B – Knowledge Base Management

An administration panel for:

- Selecting a nation.
- Selecting data categories.
- Downloading information from the EU4 Wiki.
- Previewing downloaded content.
- Editing documents.
- Assigning and correcting metadata.
- Adding documents to ChromaDB.
- Removing outdated data.

### Why One Interface?

This allows us to manage the knowledge base and use the assistant without launching separate applications.

At the same time, the modules should remain logically separate.

---

## 8. Proposed Project Structure

```text
EU4_AI_Expert/
│
├── app/
│   ├── main.py
│   ├── chat.py
│   └── knowledge_manager.py
│
├── backend/
│   ├── wiki_downloader.py
│   ├── wiki_processor.py
│   ├── embeddings.py
│   ├── rag.py
│   └── llm.py
│
├── data/
│   ├── raw/
│   │   └── ottomans/
│   │
│   └── processed/
│       └── ottomans/
│
├── chroma_db/
│
└── requirements.txt
```

This is a proposed file organization, not the final project structure.

---

## 9. Next Implementation Steps

| Stage | Task | Status |
|---|---|---|
| 1 | Choose the LLM + RAG architecture | Decided |
| 2 | Choose the primary data source | EU4 Wiki |
| 3 | Choose the first nation | Ottomans |
| 4 | Define information categories | Provisionally defined |
| 5 | Check access to the MediaWiki API | To do |
| 6 | Download articles about the Ottomans | To do |
| 7 | Clean and chunk documents | To do |
| 8 | Assign metadata automatically | To do |
| 9 | Add information to ChromaDB | To do |
| 10 | Integrate RAG with Qwen3 | To do |
| 11 | Build the user interface in Streamlit | To do |
| 12 | Build the knowledge base management interface | To do |
| 13 | Test answer quality | To do |

---

## 10. Key Decisions

**Architecture:** Python + Ollama + Qwen3 + EmbeddingGemma + ChromaDB + Streamlit.

**Data source:** Primarily the EU4 Wiki.

**First nation:** The Ottoman Empire (`TUR`).

**Initial categories:** `starting_position`, `national_ideas`, `missions`.

**Database:** A single ChromaDB collection with metadata for filtering knowledge.

**Interface:** A local Streamlit application with a chat module and a knowledge management module.

**Game integration:** Outside the current project scope.

**Fine-tuning:** Not planned at this stage.

### Immediate Next Task

**Determine how to retrieve information about the Ottoman Empire from the EU4 Wiki effectively.**

The best starting point is one article, to evaluate:

1. Whether the MediaWiki API is accessible.
2. How the downloaded data is structured.
3. Whether missions, national ideas, and starting-position information can be extracted automatically.
4. How to preserve relationships between pieces of information when splitting documents into chunks.

**At this stage, there is no need to build the entire interface or integrate the LLM. The priority is to establish a reliable process for retrieving and processing Wiki data.**
