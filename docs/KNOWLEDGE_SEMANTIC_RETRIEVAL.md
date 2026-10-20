# Optional semantic retrieval for NOX Knowledge Index

Knowledge Index continues to use SQLite FTS5 lexical retrieval when embedding settings are absent or the provider is unavailable.

To enable semantic ranking, configure these environment variables on the NOX backend service:

- `NOX_EMBEDDING_API_KEY`: secret key for an OpenAI-compatible embeddings provider.
- `NOX_EMBEDDING_MODEL`: the provider's supported embedding model ID.
- `NOX_EMBEDDING_BASE_URL`: optional API base URL; defaults to `https://api.openai.com/v1`. The service must expose `POST /embeddings`.

These settings are separate from chat model settings. A chat model or OpenRouter free chat model does not automatically provide an embeddings endpoint. Verify model availability, pricing, rate limits, and compatibility with your provider first.

When configured, new or refreshed chunks are embedded in batches and vectors are stored in the existing SQLite knowledge database. Queries are embedded and cosine similarity is blended with lexical relevance. Existing databases are migrated by adding a nullable column; old chunks without vectors remain searchable through lexical retrieval. Provider errors never block indexing or search.

Existing chunks are not automatically backfilled. Re-index or refresh a source after configuring embeddings to generate vectors for it. Keep keys in Render environment variables, never source code. The API reports semantic retrieval as active only when query and stored vectors actually participate.
