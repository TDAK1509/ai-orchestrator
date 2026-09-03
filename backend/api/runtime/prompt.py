from models.task import Task


def build_initial_user_message(task: Task) -> dict:
    return {
        "type": "user",
        "message": {"role": "user", "content": render_task_brief(task)},
    }


def render_task_brief(task: Task) -> str:
    if task.description:
        return f"{task.title}\n\n{task.description}"
    return task.title


def build_follow_up_message(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}
