from app.core.errors import APIError


def check_version(current, version):
    if not current:
        raise APIError(404, "not_found", "Resource not found")
    if current.get("version") != version:
        raise APIError(409, "version_conflict", "Resource changed; reload before retrying")


def bootstrap(repo, token, request_id):
    uid = token["uid"]

    def change(current):
        if current:
            if not current.get("isActive"):
                raise APIError(403, "account_disabled", "Account is disabled")
            return None
        return {
            "email": token.get("email"),
            "displayName": (token.get("name") or "User")[:120],
            "role": "user",
            "isActive": True,
        }

    return repo.mutate(
        "users", uid, change, actor=uid, event="user.bootstrap", request_id=request_id
    )


def update_user(repo, uid, data, actor, request_id, version):
    if uid == actor and "isActive" in data:
        raise APIError(
            409, "self_lock_forbidden", "Administrators cannot change their own active state"
        )

    def change(current):
        check_version(current, version)
        return data

    return repo.mutate(
        "users", uid, change, actor=actor, event="user.update", request_id=request_id
    )
