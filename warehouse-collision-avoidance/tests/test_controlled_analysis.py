from analyze_controlled_study import wilson
import pytest


def test_success_confidence_intervals_include_uncertainty_at_extremes():
    lo,hi=wilson(0,10)
    assert lo==0 and 0<hi<100
    lo,hi=wilson(10,10)
    assert 0<lo<100 and hi==100
    lo,hi=wilson(5,10)
    assert lo<50<hi and hi-50==pytest.approx(50-lo)
