from __future__ import annotations

import ast
import os


def get_repo_tree(directory, prefix=""):
    """Recursively generates a visual tree of the directory, showing only Python files."""
    tree = []
    try:
        entries = sorted(os.listdir(directory))
        entries = [
            e for e in entries if not e.startswith(".git") and not e.endswith(".pyc")
        ]
        for index, entry in enumerate(entries):
            entry_path = os.path.join(directory, entry)
            is_last = index == len(entries) - 1

            # Only include directories and .py files
            if os.path.isdir(entry_path) or entry.endswith(".py"):
                tree.append(f"{prefix}{'└── ' if is_last else '├── '}{entry}")
                if os.path.isdir(entry_path):
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    tree.extend(get_repo_tree(entry_path, new_prefix))
    except PermissionError:
        pass
    return tree


def extract_info_from_python_file(filepath):
    """Extracts imports, global variables, __main__ section, classes, and methods."""
    with open(filepath, "r", encoding="utf-8") as file:
        source_code = file.read()

    tree = ast.parse(source_code)

    imports = []
    global_initiations = []
    main_section = []
    classes = {}

    for node in ast.walk(tree):
        # Handle imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.unparse(node))

        # Handle global assignments
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            global_initiations.append(ast.unparse(node))

        # Handle __main__ section
        elif isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            if (
                isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"
                and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value == "__main__"
            ):
                main_section.append(ast.unparse(node))

        # Handle class definitions
        elif isinstance(node, ast.ClassDef):
            methods = {}
            for sub_node in node.body:
                if isinstance(
                    sub_node,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):  # Supports async methods too
                    method_signature = extract_function_signature(sub_node)
                    methods[sub_node.name] = method_signature
            classes[node.name] = methods

    return imports, global_initiations, main_section, classes


def extract_function_signature(func_node):
    """Extract function/method signature including parameter types and return type."""
    params = []
    for arg in func_node.args.args:
        arg_name = arg.arg
        arg_type = ast.unparse(arg.annotation) if arg.annotation else "Any"
        params.append(f"{arg_name}: {arg_type}")

    return_type = ast.unparse(func_node.returns) if func_node.returns else "None"

    return f"({', '.join(params)}) -> {return_type}"


def process_directory(directory, output_filename="repository_summary.txt"):
    """Processes all Python files recursively and writes the summary to a single file."""
    repo_tree = "\n".join(get_repo_tree(directory))

    with open(output_filename, "w", encoding="utf-8") as output_file:
        output_file.write("Repository Structure:\n")
        output_file.write(repo_tree + "\n\n")

        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".py") and file != os.path.basename(
                    __file__,
                ):  # Avoid this script
                    filepath = os.path.join(root, file)
                    (
                        imports,
                        global_initiations,
                        main_section,
                        classes,
                    ) = extract_info_from_python_file(filepath)

                    output_file.write("=" * 80 + "\n")
                    output_file.write(f"File: {filepath}\n")
                    output_file.write("=" * 80 + "\n\n")

                    output_file.write("Imports:\n")
                    output_file.write("\n".join(imports) + "\n\n")

                    output_file.write("Global Initiations:\n")
                    output_file.write("\n".join(global_initiations) + "\n\n")

                    output_file.write("__main__ Section:\n")
                    output_file.write("\n".join(main_section) + "\n\n")

                    output_file.write("Classes and Methods:\n")
                    for class_name, methods in classes.items():
                        output_file.write(f"Class: {class_name}\n")
                        for method_name, signature in methods.items():
                            output_file.write(f"  {method_name} {signature}\n")
                    output_file.write("\n\n")


if __name__ == "__main__":
    target_directory = "./"  # Change this to your directory path
    process_directory(target_directory)
