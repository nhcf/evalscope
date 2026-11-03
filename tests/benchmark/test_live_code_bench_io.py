# Copyright (c) Alibaba, Inc. and its affiliates.
"""LCB标准输入输出回归：正常、二进制及混合I/O，错误判分和超时保护。

每个答案在独立进程执行，防止run_test的reliability_guard污染测试主进程。
运行：python -m unittest tests.benchmark.test_live_code_bench_io -v
"""
import json
import multiprocessing as mp
import unittest

from evalscope.benchmarks.live_code_bench import testing_util as t


def child(queue, sample, code, timeout):
    try:
        values, metadata = t.run_test(sample, code, debug=False, timeout=timeout)
        queue.put({'results': [int(x) for x in values], 'metadata': metadata})
    except BaseException as e:
        queue.put({'error': repr(e)})


def check(name, code, inputs, outputs, expect=True, timeout=6, fn_name=None):
    sample = {'input_output': json.dumps({'inputs': inputs, 'outputs': outputs, 'fn_name': fn_name})}
    ctx = mp.get_context('fork')
    queue = ctx.Queue()
    proc = ctx.Process(target=child, args=(queue, sample, code, timeout))
    proc.start()
    try:
        result = queue.get(timeout=(timeout+1)*len(inputs)+10)
    finally:
        proc.join(2)
        if proc.is_alive(): proc.kill(); proc.join()
        queue.close()
    values = result.get('results', [])
    passed = bool(values) and all(x == 1 for x in values)
    assert 'error' not in result, result
    assert passed == expect, (name,result)
    if name == 'timeout': assert -3 in values, result


class TestLiveCodeBenchIO(unittest.TestCase):

    def test_stdio_and_scoring(self):
        tests = {
            'text': 'print(int(input())+int(input()))',
            'binary_read': 'import sys\nprint(sum(map(int,sys.stdin.buffer.read().split())))',
            'binary_lines': 'import sys\na=int(sys.stdin.buffer.readline())\nb=int(sys.stdin.buffer.readline())\nprint(a+b)',
            'mixed_read': 'import sys\na=int(sys.stdin.buffer.readline())\nb=int(sys.stdin.readline())\nprint(a+b)',
            'binary_write': "import sys\nsys.stdout.buffer.write(b'3\\n')",
            'exit': 'import sys\nprint(3)\nsys.exit(0)',
            'close_stdout': 'import sys\nprint(3)\nsys.stdout.close()',
        }
        for name, code in tests.items():
            with self.subTest(name=name):
                check(name, code, ['1\n2\n'], ['3\n'])
        check('mixed_write',"import sys\nprint(1)\nsys.stdout.buffer.write(b'2\\n')\nprint(3)",[''],['1\n2\n3\n'])
        check('wrong_answer','print(4)',[''],['3'],expect=False)
        check('timeout','while True: pass',[''],['3'],expect=False,timeout=1)


if __name__ == "__main__":
    unittest.main()
