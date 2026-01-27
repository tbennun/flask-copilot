from fastapi import WebSocket
from callback_logger import CallbackLogger

from backend_helper_funcs import Node
from retrosynthesis.context import RetrosynthesisContext
from moleculedb.molecules import is_purchasable


async def set_reaction_alternative(
    node: Node,
    alternative_id: str,
    context: RetrosynthesisContext,
    websocket: WebSocket,
):
    """
    Sets a reaction alternative

    :param node: Parent node to reset the reaction thereof
    :param alternative_id: The unique ID of the alternative to choose
    :param context: Retrosynthesis context object
    :param websocket: Websocket to client
    """
    clogger = CallbackLogger(websocket, source="set_reaction_alternative")
    assert node.reaction is not None
    assert node.reaction.alternatives is not None
    try:
        alternative = next(
            a for a in node.reaction.alternatives if a.id == alternative_id
        )
    except StopIteration:
        await clogger.info(f"Alternative {alternative_id} not found for {node.id}")
        await websocket.send_json({"type": "complete"})
        return

    node.reaction.hoverInfo = alternative.hoverInfo

    # Clear subtree and levels for layouting
    await context.delete_subtree(node.id, websocket)

    # Update reaction information
    for alt in node.reaction.alternatives:
        if alt.status == "active":
            alt.status = "available"
    alternative.status = "active"
    if alternative.type == "ai":
        node.reaction.label = "FLASK AI"
        node.reaction.highlight = "red"
    elif alternative.type == "template":
        node.reaction.label = "Template"
        node.reaction.highlight = "yellow"
    elif alternative.type == "exact":
        node.reaction.label = "Exact"
        node.reaction.highlight = "normal"

    node.highlight = "normal"
    await context.update_node(node, websocket)

    # Loop over new nodes/edges (one level only)
    if len(alternative.pathway) > 1:
        for smiles, label in zip(
            alternative.pathway[1].smiles, alternative.pathway[1].label
        ):
            mol_sources = is_purchasable(smiles)
            if mol_sources:
                purchasable_str = f"Yes (via {', '.join(mol_sources)})"
            else:
                purchasable_str = "No"

            child_node = Node(
                id=context.new_node_id(),
                smiles=smiles,
                label=label,
                hoverInfo=f"""# Molecule
**SMILES:** {smiles}

**Purchasable**? {purchasable_str}""",
                level=node.level + 1,
                parentId=node.id,
            )
            await context.add_node(child_node, node, websocket)

    await websocket.send_json({"type": "complete"})
