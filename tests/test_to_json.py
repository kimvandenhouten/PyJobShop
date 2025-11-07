from numpy.testing import assert_equal

from benchmarks.test_benchmarks import build_lawrence_instance
from pyjobshop import Model, ProblemData
from pyjobshop.ProblemData import resource_filter
from pyjobshop.utils import to_json


def test_to_json():
    model: Model = build_lawrence_instance()
    result = model.solve(display=False)

    output_location = "tests/data/model.json"

    # Create the original model data
    pd: ProblemData = model.data()
    json_str = to_json(pd, resource_filter) + "\n"
    with open(output_location, "w", encoding="utf-8") as f:
        f.write(json_str)

    problem_data = ProblemData.from_json("tests/data/model.json")
    model_new = Model.from_data(problem_data)
    result2 = model_new.solve(display=False)

    assert_equal(result.objective, result2.objective)
