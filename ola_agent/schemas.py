from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid')


class Route(StrictModel):
    destination: Literal['sql','etl','clarify']
    message: str = Field(description='Short routing explanation or clarification question')


class SQLProposal(StrictModel):
    sql: str = Field(max_length=8000)
    explanation: str


class Review(StrictModel):
    approved: bool
    feedback: str


class Filter(StrictModel):
    column: str
    operator: Literal['eq','ne','gt','gte','lt','lte']
    value: str | float | int


class ETLAction(StrictModel):
    action: Literal['inspect','extract','filter','aggregate','export','finish']
    source: Literal['pokemon'] = 'pokemon'
    filters: list[Filter] = Field(default_factory=list,max_length=5)
    group_by: list[str] = Field(default_factory=list,max_length=3)
    metric: str = ''
    aggregation: Literal['count','sum','mean','min','max'] = 'count'
    format: Literal['csv','json'] = 'csv'
    message: str = ''
