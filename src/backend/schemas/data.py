from pydantic import BaseModel

class Students(BaseModel):
    id: int
    name: str
    age: str



student = {
    "id": 1,
    "name": "nikita",
    "age": 1000000000,
}

studen2 = Students.model_validate(student)

print(student.id)