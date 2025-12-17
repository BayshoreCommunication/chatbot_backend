from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Literal, Union
from datetime import datetime
from bson import ObjectId
from pydantic_core import CoreSchema, core_schema


class PyObjectId(str):
    """Custom type for handling MongoDB ObjectId as string"""
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Any
    ) -> CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema([
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.validate),
                ])
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            ),
        )

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


# Nested Models
class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    availability: Optional[str] = None
    social_media: Optional[Dict[str, str]] = Field(default_factory=dict, alias="socialMedia")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class FAQ(BaseModel):
    question: str
    answer: str
    category: Optional[str] = None


class AIChunk(BaseModel):
    type: str
    title: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StructuredData(BaseModel):
    company_overview: Optional[str] = Field(None, alias="companyOverview")
    tagline: Optional[str] = None
    service_areas: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="serviceAreas")
    services: Optional[List[Union[str, Dict[str, Any]]]] = Field(default_factory=list)
    products: Optional[List[Union[str, Dict[str, Any]]]] = Field(default_factory=list)
    contact_info: Optional[ContactInfo] = Field(default_factory=ContactInfo, alias="contactInfo")
    key_features: Optional[List[Union[str, Dict[str, Any]]]] = Field(default_factory=list, alias="keyFeatures")
    pricing: Optional[Union[str, Dict[str, Any]]] = None
    faqs: Optional[List[Union[FAQ, Dict[str, Any]]]] = Field(default_factory=list)
    case_results: Optional[List[Dict[str, Any]]] = Field(default_factory=list, alias="caseResults")
    team: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    testimonials: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    process_steps: Optional[List[Dict[str, Any]]] = Field(default_factory=list, alias="processSteps")
    additional_info: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="additionalInfo")
    chatbot_responses: Optional[Dict[str, str]] = Field(default_factory=dict, alias="chatbotResponses")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )


class Source(BaseModel):
    type: Literal["website", "web_search", "manual", "document", "analysis"]
    url: Optional[str] = None
    search_query: Optional[str] = Field(None, alias="searchQuery")
    file_path: Optional[str] = Field(None, alias="filePath")
    content: str
    processed_at: datetime = Field(default_factory=datetime.now, alias="processedAt")
    chunk_count: Optional[int] = Field(None, alias="chunkCount")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()}
    )


class UpdateHistory(BaseModel):
    version: int
    updated_at: datetime = Field(alias="updatedAt")
    total_sources: int = Field(alias="totalSources")
    quality: Literal["high", "medium", "low"]
    quality_percentage: float = Field(alias="qualityPercentage")
    changes: str

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()}
    )


class Metadata(BaseModel):
    total_sources: int = Field(0, alias="totalSources")
    total_chunks: Optional[int] = Field(0, alias="totalChunks")
    last_updated: datetime = Field(default_factory=datetime.now, alias="lastUpdated")
    version: int = 1
    model: str = "gpt-4"
    token_count: Optional[int] = Field(None, alias="tokenCount")
    quality: Literal["high", "medium", "low"] = "medium"
    quality_percentage: float = Field(0.0, alias="qualityPercentage")
    update_history: Optional[List[UpdateHistory]] = Field(default_factory=list, alias="updateHistory")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()}
    )


# Main Knowledge Base Models
class KnowledgeBaseBase(BaseModel):
    user_id: PyObjectId = Field(alias="userId")
    company_name: str = Field(alias="companyName")
    sources: List[Source] = Field(default_factory=list)
    structured_data: StructuredData = Field(default_factory=StructuredData, alias="structuredData")
    raw_content: Optional[str] = Field(default="", alias="rawContent")
    ai_chunks: Optional[List[AIChunk]] = Field(default_factory=list, alias="aiChunks")
    vector_store_id: Optional[str] = Field(None, alias="vectorStoreId")
    file_ids: Optional[List[str]] = Field(default_factory=list, alias="fileIds")
    metadata: Metadata = Field(default_factory=Metadata)
    status: Literal["active", "processing", "failed", "archived"] = "processing"

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()}
    )


class KnowledgeBaseCreate(KnowledgeBaseBase):
    """Model for creating a new knowledge base"""
    pass


class KnowledgeBaseUpdate(BaseModel):
    """Model for updating knowledge base - all fields optional"""
    company_name: Optional[str] = Field(None, alias="companyName")
    sources: Optional[List[Source]] = None
    structured_data: Optional[StructuredData] = Field(None, alias="structuredData")
    raw_content: Optional[str] = Field(None, alias="rawContent")
    vector_store_id: Optional[str] = Field(None, alias="vectorStoreId")
    file_ids: Optional[List[str]] = Field(None, alias="fileIds")
    metadata: Optional[Metadata] = None
    status: Optional[Literal["active", "processing", "failed", "archived"]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()}
    )


class KnowledgeBaseInDB(KnowledgeBaseBase):
    """Model representing knowledge base in database with _id"""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.now, alias="createdAt")
    updated_at: datetime = Field(default_factory=datetime.now, alias="updatedAt")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()}
    )


class KnowledgeBaseResponse(KnowledgeBaseInDB):
    """Model for API responses"""
    pass