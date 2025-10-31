from numpy.testing import assert_equal

from benchmarks.test_benchmarks import build_lawrence_instance
from pyjobshop import Model, ProblemData


def test_jsp_lawrence():
    model = build_lawrence_instance()
    result = model.solve(display=False)

    # Create the original model data
    m = model.data()
    m.to_json("tests/data/model.json")
    problem_data = ProblemData.from_json("tests/data/model.json")
    model_new = Model.from_data(problem_data)
    result2 = model_new.solve(display=False)

    assert_equal(result.objective, result2.objective)
