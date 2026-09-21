import asyncio

from inferlingo import ExactUnifier, KnowledgeBase, Provenance


async def main() -> None:
    kb = KnowledgeBase.from_file("examples/python_lint_rules.nl", unifier=ExactUnifier())
    kb.add_fact(
        "Function {fn} catches a broad exception",
        fn="process_order",
        provenance=Provenance(source="orders.py", line=81, kind="python-ast"),
    )
    kb.add_fact(
        "Function {fn} has an exception path that does not re-raise",
        fn="process_order",
        provenance=Provenance(source="orders.py", line=84, kind="python-ast"),
    )
    result = await kb.ask("Function {fn} may swallow errors?")
    for solution in result.solutions:
        print(solution.bindings, solution.proof.render())


if __name__ == "__main__":
    asyncio.run(main())
