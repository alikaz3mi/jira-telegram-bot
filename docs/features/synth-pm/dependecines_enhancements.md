This implemenation doesn't seem to be working correctly.

DepartmentDependencyCalculator.calculate_department_deadlines(
            feature.deadline,
            dept_deps_dict,
            department_hours,
            holidays,
        )

It returns 

{'Frontend': {'start': datetime.datetime(2025, 11, 11, 0, 0), 'end': datetime.datetime(2025, 11, 12, 0, 0)}, 'UI/UX': {'start': datetime.datetime(2025, 11, 11, 0, 0), 'end': datetime.datetime(2025, 11, 12, 0, 0)}, 'Backend': {'start': datetime.datetime(2025, 11, 10, 0, 0), 'end': datetime.datetime(2025, 11, 11, 0, 0)}, 'AI': {'start': datetime.datetime(2025, 11, 5, 0, 0), 'end': datetime.datetime(2025, 11, 10, 0, 0)}}

deadline: datetime.datetime(2025, 11, 12, 0, 0)

dept_deps_dict
{'Frontend': ['UI / UX', 'Backend'], 'Backend': ['AI']}

department_hours
{'Frontend': 6, 'Backend': 6, 'UI/UX': 1, 'AI': 30}

Frontend depends on backend and UI. Their total time is 7 hours. if total time is more than two hours, consider implementation for the next day

