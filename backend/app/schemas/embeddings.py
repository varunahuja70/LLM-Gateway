from pydantic import BaseModel, ConfigDict


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    input: str | list[str] | list[int] | list[list[int]]
    model: str | None = None
    encoding_format: str | None = "float"
    dimensions: int | None = None
    user: str | None = None


class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: list[float]


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingData]
    model: str
    usage: EmbeddingUsage
