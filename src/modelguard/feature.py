"""The reusable feature under test: email text in, typed prediction out."""
from pydantic import Field, ValidationError
from .models import Strict
from .providers import ProviderFailure

class EmailInput(Strict):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    email: str = Field(min_length=1,max_length=12000)

async def classify_email(email, prompt, provider, *, case_id='interactive'):
    sample=EmailInput(id=case_id,email=email)
    observation=await provider.classify(prompt,sample)
    from .models import Prediction
    try:
        prediction=Prediction.model_validate_json(observation.raw)
    except ValidationError:
        raise ProviderFailure('invalid_prediction',observation) from None
    return prediction,observation
