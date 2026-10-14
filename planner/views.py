import json

from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .errors import PlanError
from .models import RoutePlan, Station
from .service import plan


@require_GET
def home(request):
    return render(request, "planner/home.html")


@require_GET
def health(request):
    return JsonResponse({"status": "ok", "priced_stations": Station.objects.count()})


@csrf_exempt
@require_POST
def create_plan(request):
    if request.content_type != "application/json":
        return JsonResponse(
            {
                "error": {
                    "code": "unsupported_media_type",
                    "message": "Send application/json.",
                }
            },
            status=415,
        )
    try:
        body = request.body
    except RequestDataTooBig:
        body = None
    if body is None or len(body) > 16384:
        return JsonResponse(
            {
                "error": {
                    "code": "body_too_large",
                    "message": "Request body exceeds 16 KiB.",
                }
            },
            status=413,
        )
    try:
        payload = json.loads(body)
        record = plan(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError, ValueError):
        return JsonResponse(
            {"error": {"code": "invalid_json", "message": "Provide valid JSON."}},
            status=400,
        )
    except PlanError as e:
        return JsonResponse({"error": {"code": e.code, "message": e.message}}, status=e.status)
    return JsonResponse(
        {
            "id": str(record.id),
            **record.result,
            "map_url": request.build_absolute_uri(reverse("map", args=[record.id])),
        },
        status=201,
    )


@require_GET
def map_view(request, plan_id):
    record = get_object_or_404(RoutePlan, pk=plan_id)
    return render(request, "planner/map.html", {"result": record.result})
