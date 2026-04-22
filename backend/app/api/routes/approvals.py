from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("")
def list_approvals() -> dict[str, object]:
    return {"items": [], "status": "No pending approvals"}


@router.post("/{approval_id}/approve")
def approve_request(approval_id: str) -> dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Approval {approval_id} cannot be approved before Telegram gate is implemented.",
    )


@router.post("/{approval_id}/reject")
def reject_request(approval_id: str) -> dict[str, str]:
    return {"approvalId": approval_id, "status": "rejected"}
