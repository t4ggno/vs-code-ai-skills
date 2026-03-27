import sys
import math

def calculate(expression):
    safe_dict = {
        '__builtins__': None,
        'math': math,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'log': math.log,
        'sqrt': math.sqrt,
        'pi': math.pi,
        'e': math.e,
        'abs': abs
    }

    try:
        result = eval(expression, safe_dict)
        return result
    except Exception as e:
        return f"Error evaluating expression: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python calculate.py '<math_expression>'")
        sys.exit(1)

    expr = sys.argv[1]
    ans = calculate(expr)
    print(f"Result: {ans}")
