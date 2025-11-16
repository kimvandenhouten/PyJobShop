import json

from numpy.testing import assert_equal

from benchmarks.test_benchmarks import build_lawrence_instance
from pyjobshop import Model, ProblemData, ProblemDataDecoder
from pyjobshop.utils import DataclassEncoder


def test_to_json():
    model: Model = build_lawrence_instance()
    result = model.solve(display=False)

    output_location = "tests/data/model.json"

    # Create the original model data
    pd: ProblemData = model.data()
    json_str = json.dumps(pd, cls=DataclassEncoder, indent=2) + "\n"
    with open(output_location, "w", encoding="utf-8") as f:
        f.write(json_str)

    problem_data: ProblemData
    with open(output_location, "r", encoding="utf-8") as f:
        problem_data = json.load(f, cls=ProblemDataDecoder)
    model_new = Model.from_data(problem_data)
    result2 = model_new.solve(display=False)

    assert_equal(result.objective, result2.objective)
