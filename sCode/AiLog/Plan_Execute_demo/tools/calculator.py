
def calculator(num1: float, num2: float, operator: str) -> str:
    """四则运算计算器"""
    if operator == "+":
        res = num1 + num2
    elif operator == "-":
        res = num1 - num2
    elif operator == "*":
        res = num1 * num2
    elif operator == "/":
        if num2 == 0:
            return "错误：除数不能为0"
        res = num1 / num2
    else:
        return f"不支持运算符：{operator}"
    return f"计算结果：{num1} {operator} {num2} = {res}"