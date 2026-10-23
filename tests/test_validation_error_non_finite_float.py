from typing import Annotated

import pytest
from fastapi import Body, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, model_validator

app = FastAPI()


class GreaterThan(BaseModel):
    amount: float = Field(gt=0)


class Finite(BaseModel):
    amount: float = Field(allow_inf_nan=False)


class Unconstrained(BaseModel):
    amount: float


class AlwaysFails(BaseModel):
    a: float
    b: list[float]

    @model_validator(mode="before")
    @classmethod
    def always_fail(cls, data):
        raise ValueError("always fails")


@app.post("/greater-than")
def greater_than(item: GreaterThan):
    return item  # pragma: no cover


@app.post("/finite")
def finite(item: Finite):
    return item  # pragma: no cover


@app.post("/unconstrained")
def unconstrained(item: Unconstrained):
    return {"ok": True}


@app.post("/nested")
def nested(item: AlwaysFails):
    return item  # pragma: no cover


@app.post("/body-param")
def body_param(amount: Annotated[float, Body(gt=0, embed=True)]):
    return {"amount": amount}  # pragma: no cover


client = TestClient(app)

JSON_HEADERS = {"content-type": "application/json"}


@pytest.mark.parametrize(
    "token,expected_input",
    [
        ("NaN", "nan"),
        ("-Infinity", "-inf"),
    ],
)
def test_non_finite_json_float_fails_constraint_returns_422(
    token: str, expected_input: str
):
    response = client.post(
        "/greater-than",
        content=f'{{"amount": {token}}}'.encode(),
        headers=JSON_HEADERS,
    )
    assert response.status_code == 422, response.text
    assert response.json() == {
        "detail": [
            {
                "type": "greater_than",
                "loc": ["body", "amount"],
                "msg": "Input should be greater than 0",
                "input": expected_input,
                "ctx": {"gt": 0.0},
            }
        ]
    }


@pytest.mark.parametrize(
    "token,expected_input",
    [
        ("NaN", "nan"),
        ("Infinity", "inf"),
        ("-Infinity", "-inf"),
    ],
)
def test_non_finite_json_float_with_allow_inf_nan_false_returns_422(
    token: str, expected_input: str
):
    response = client.post(
        "/finite",
        content=f'{{"amount": {token}}}'.encode(),
        headers=JSON_HEADERS,
    )
    assert response.status_code == 422, response.text
    assert response.json() == {
        "detail": [
            {
                "type": "finite_number",
                "loc": ["body", "amount"],
                "msg": "Input should be a finite number",
                "input": expected_input,
            }
        ]
    }


def test_non_finite_json_float_nested_in_error_input_returns_422():
    # The error `input` is the whole body, so non-finite floats are nested in it.
    response = client.post(
        "/nested",
        content=b'{"a": NaN, "b": [Infinity, 1.5, -Infinity]}',
        headers=JSON_HEADERS,
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert len(detail) == 1
    assert detail[0]["loc"] == ["body"]
    assert detail[0]["input"] == {"a": "nan", "b": ["inf", 1.5, "-inf"]}


def test_non_finite_json_float_in_embedded_body_param_returns_422():
    response = client.post(
        "/body-param",
        content=b'{"amount": NaN}',
        headers=JSON_HEADERS,
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"] == ["body", "amount"]
    assert response.json()["detail"][0]["input"] == "nan"


def test_finite_float_input_is_unchanged_in_validation_error():
    response = client.post("/greater-than", json={"amount": -1})
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["input"] == -1


def test_unconstrained_float_still_accepts_nan():
    # Not changed by the fix: a plain `float` accepts NaN.
    response = client.post(
        "/unconstrained", content=b'{"amount": NaN}', headers=JSON_HEADERS
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}