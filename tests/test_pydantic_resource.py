from decimal import Decimal
from pydantic import BaseModel, field_validator
from pyntral.validation import validate_payload
from pyntral.orm import AdminError

class PriceRules(BaseModel):
    price: Decimal | None = None
    @field_validator("price")
    @classmethod
    def validate_price(cls, p):
        if p is not None and p <= 0: raise ValueError("sensitive text must not be returned")
        return p

def test_validation_preserves_authorized_fields_and_converts_declared_types():
    assert validate_payload(PriceRules,{"price":"8.2","name":"test"})=={
        "price": Decimal("8.2"),"name":"test"}

def test_validation_hides_input_and_exception_details():
    import pytest
    with pytest.raises(AdminError) as exc:
        validate_payload(PriceRules,{"price":"-1","name":"test"})
    assert exc.value.status == 422
    assert exc.value.details=={"fields":["price"]}
    assert "sensitive text" not in exc.value.message
    assert "-1" not in str(exc.value.details)
