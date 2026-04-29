"""
Keyword registry — coverage map derived dynamically from source_truth.json.
Keyword tagged "~foo" in a bullet = implicit coverage for "foo".
Keyword tagged "foo"  in a bullet = bullet-level coverage for "foo".
Keyword in skills section only     = skills-level coverage.
Priority: bullet > implicit > skills.
"""

import json
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "source_truth.json"


def _build_master() -> dict[str, str]:
    data = json.loads(_DATA_PATH.read_text())
    coverage: dict[str, str] = {}

    def _set(kw: str, level: str):
        priority = {"bullet": 2, "implicit": 1, "skills": 0}
        if kw not in coverage or priority[level] > priority[coverage[kw]]:
            coverage[kw] = level

    # Bullet-level and implicit coverage from work experience
    for role in data.get("work_experience", []):
        for bullet in role.get("bullets", []):
            for kw in bullet.get("keywords", []):
                if kw.startswith("~"):
                    _set(kw[1:], "implicit")
                else:
                    _set(kw, "bullet")

    # Bullet-level and implicit coverage from projects
    for project in data.get("projects", []):
        for bullet in project.get("bullets", []):
            for kw in bullet.get("keywords", []):
                if kw.startswith("~"):
                    _set(kw[1:], "implicit")
                else:
                    _set(kw, "bullet")

    # Skills-level coverage (only if not already backed by a bullet)
    skills = data.get("skills", {})
    for kw_list in skills.values():
        for kw in kw_list:
            _set(kw, "skills")

    return coverage


# Rebuilt on import — cheap since it's just a file read + dict build
MASTER_KEYWORDS: dict[str, str] = _build_master()


# ── Synonym normalizer ─────────────────────────────────────────────────────────
SYNONYM_MAP: dict[str, str] = {
    # TypeScript
    "ts":                           "typescript",
    "ts/js":                        "typescript",

    # JavaScript
    "js":                           "javascript",
    "es6":                          "javascript",
    "ecmascript":                   "javascript",
    "vanilla js":                   "javascript",

    # Python
    "python3":                      "python",
    "py":                           "python",

    # Java + Spring
    "java 11":                      "java",
    "java 17":                      "java",
    "java 21":                      "java",
    "spring":                       "java",
    "spring boot":                  "java",
    "jvm":                          "java",
    "maven":                        "java",
    "gradle":                       "java",

    # C++
    "cpp":                          "c++",

    # C# / .NET
    "csharp":                       "c#",
    "dotnet":                       "c#",
    ".net":                         "c#",
    "asp.net":                      "c#",

    # SQL
    "relational database":          "sql",
    "rdbms":                        "sql",
    "relational":                   "sql",

    # React
    "react.js":                     "react",
    "reactjs":                      "react",
    "react js":                     "react",

    # Next.js
    "nextjs":                       "next.js",
    "next js":                      "next.js",

    # Node.js
    "nodejs":                       "node.js",
    "node":                         "node.js",

    # Express
    "express":                      "node.js",   # Express implies Node.js
    "express.js":                   "node.js",
    "expressjs":                    "node.js",

    # REST API
    "rest":                         "rest api",
    "restful":                      "rest api",
    "restful api":                  "rest api",
    "restful apis":                 "rest api",
    "rest apis":                    "rest api",
    "rest-based":                   "rest api",
    "http api":                     "rest api",
    "openapi":                      "rest api",
    "swagger":                      "rest api",

    # GraphQL
    "gql":                          "graphql",

    # WebSockets
    "websocket":                    "websockets",
    "web sockets":                  "websockets",
    "web socket":                   "websockets",
    "socket.io":                    "websockets",

    # gRPC  (not on resume → real gap)
    "grpc":                         "grpc",
    "protobuf":                     "grpc",
    "protocol buffers":             "grpc",

    # MongoDB
    "mongo":                        "mongodb",
    "mongoose":                     "mongodb",

    # PostgreSQL
    "postgres":                     "postgresql",
    "psql":                         "postgresql",

    # MySQL
    "mariadb":                      "mysql",

    # Redis
    "redis cache":                  "redis",
    "elasticache":                  "redis",

    # NoSQL
    "document database":            "nosql",
    "document store":               "nosql",

    # Docker
    "containers":                   "docker",
    "containerization":             "docker",
    "container":                    "docker",
    "docker compose":               "docker",

    # CI/CD
    "ci":                           "ci/cd",
    "cd":                           "ci/cd",
    "continuous integration":       "ci/cd",
    "continuous deployment":        "ci/cd",
    "continuous delivery":          "ci/cd",
    "github actions":               "ci/cd",
    "jenkins":                      "ci/cd",
    "gitlab ci":                    "ci/cd",
    "circleci":                     "ci/cd",

    # Git
    "github":                       "git",
    "gitlab":                       "git",
    "bitbucket":                    "git",
    "version control":              "git",

    # AWS
    "amazon web services":          "aws",
    "ec2":                          "aws",
    "s3":                           "aws",
    "lambda":                       "aws",
    "rds":                          "aws",
    "ecs":                          "aws",
    "cloudfront":                   "aws",
    "sqs":                          "aws",
    "sagemaker":                    "aws",
    "cloud":                        "aws",

    # Kubernetes (not on resume → real gap)
    "k8s":                          "kubernetes",
    "kubernetes":                   "kubernetes",
    "openshift":                    "kubernetes",
    "helm":                         "kubernetes",
    "container orchestration":      "kubernetes",

    # JWT / Auth
    "json web token":               "jwt",
    "json web tokens":              "jwt",
    "token auth":                   "jwt",
    "token-based auth":             "jwt",
    "bearer token":                 "jwt",

    # OAuth
    "oauth2":                       "oauth",
    "oauth 2.0":                    "oauth",
    "sso":                          "oauth",
    "oidc":                         "oauth",
    "openid":                       "oauth",

    # RBAC
    "role-based access control":    "rbac",
    "role based access control":    "rbac",
    "access control":               "rbac",

    # AI / ML
    "machine learning":             "ai",
    "artificial intelligence":      "ai",
    "ml":                           "ai",
    "nlp":                          "ai",
    "openai":                       "ai",
    "generative ai":                "ai",
    "gen ai":                       "ai",

    # Whisper / speech
    "openai whisper":               "whisper",
    "speech recognition":           "whisper",
    "asr":                          "speech-to-text",
    "automatic speech recognition": "speech-to-text",
    "transcription":                "whisper",

    # RAG
    "retrieval augmented generation":  "rag",
    "retrieval-augmented generation":  "rag",
    "retrieval-augmented":             "rag",
    "vector search":                   "rag",
    "semantic search":                 "rag",
    "vector database":                 "rag",
    "embedding":                       "rag",
    "pinecone":                        "rag",
    "weaviate":                        "rag",
    "pgvector":                        "rag",

    # LLM
    "large language model":         "llm",
    "large language models":        "llm",
    "foundation model":             "llm",
    "gpt":                          "llm",

    # Architecture
    "event-driven":                 "event sourcing",
    "event driven":                 "event sourcing",
    "event-sourced":                "event sourcing",
    "microservice":                 "microservices",
    "micro-services":               "microservices",
    "service-oriented":             "microservices",
    "scalability":                  "distributed systems",
    "scalable":                     "distributed systems",
    "high availability":            "distributed systems",
    "distributed":                  "distributed systems",
    "fault tolerance":              "distributed systems",

    # Caching
    "cache":                        "caching",
    "memoization":                  "caching",

    # Pub/sub / messaging
    "kafka":                        "pub/sub",
    "rabbitmq":                     "pub/sub",
    "message queue":                "pub/sub",
    "message broker":               "pub/sub",
    "pubsub":                       "pub/sub",
    "event stream":                 "pub/sub",

    # Real-time
    "real time":                    "real-time",
    "live":                         "real-time",

    # CRDT
    "conflict-free replicated data type": "crdt",

    # Concurrency
    "concurrent":                   "concurrency",
    "thread-safe":                  "concurrency",
    "async":                        "concurrency",
    "asynchronous":                 "concurrency",

    # Unity
    "unity3d":                      "unity",

    # Swift / Apple
    "xcode":                        "swift",
    "ios":                          "swift",
    "macos":                        "swift",
    "apple vision pro":             "visionos",
    "vision pro":                   "visionos",
    "core ml":                      "coreml",
    "on-device ml":                 "coreml",
}


def normalize(term: str) -> str:
    t = term.strip().lower()
    return SYNONYM_MAP.get(t, t)


def coverage(keyword: str) -> str | None:
    return MASTER_KEYWORDS.get(keyword.strip().lower())


def reload():
    """Call after editing source_truth.json to refresh the in-memory map."""
    global MASTER_KEYWORDS
    MASTER_KEYWORDS = _build_master()
