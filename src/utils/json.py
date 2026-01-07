# std
from typing import Any

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonValue] | dict[str, JsonValue]


def is_json_serializable(obj: Any, current_path: list[str | int] = []) -> list[str]:
    """
    value がプロパティとして合法かどうかチェックし、問題のある要素のパスをリストで返す。
    list, dict みたいな構造オブジェクトの場合は再帰的に全要素をチェックする。
    問題のある要素の情報をリストで返すので、空のリストが返ってきたら合法ということ
    """
    if isinstance(obj, (list, tuple)):
        return [
            e
            for i, v in enumerate(obj)
            for e in is_json_serializable(v, current_path + [i])
        ]
    elif isinstance(obj, dict):
        return [
            e
            for k, v in obj.items()
            for e in is_json_serializable(v, current_path + [k])
        ]
    elif isinstance(obj, (int, float, str)) or obj is None:
        return []
    else:
        error_path_str = "root"
        for i, p in enumerate(current_path):
            if isinstance(p, str):
                error_path_str += f".{p}"
            elif isinstance(p, int):
                error_path_str += f"[{p}]"
            else:
                error_path_str += "???" if i == 0 else ".???"
        return [f"path={error_path_str}, type={type(obj)}, value={str(obj)[:20]}"]
