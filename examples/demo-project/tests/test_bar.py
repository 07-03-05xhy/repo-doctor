"""bar 模块的测试。"""
from src.foo.bar import short_function


def test_short_function():
    assert short_function() == 1
