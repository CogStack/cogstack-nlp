from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.shortcuts import render
import json
import random
import os

from medcat import __version__ as medcat_version

from .models import Question, UserAttempt, APIKey, cooldown_minutes


def get_client_identifier(request):
    """Get a unique identifier for the client (IP-based)"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_number_of_questions() -> int:
    return int(os.environ.get("MEDCAT_DEMO_MIN_QUESTIONS", 5))


@csrf_exempt
@require_http_methods(["GET"])
def get_questionnaire(request):
    """Get N random questions from the pool"""
    identifier = get_client_identifier(request)

    # Check if user can attempt
    if not UserAttempt.can_attempt(identifier):
        cooldown = UserAttempt.get_cooldown_remaining(identifier)
        return render(request, 'questionnaire/cooldown.html', {
            'cooldown_seconds': cooldown,
            'cooldown_minutes': cooldown_minutes,
            'medcat_version': medcat_version,
        })


    # Get random questions (adjust N as needed)
    N = get_number_of_questions()
    questions = list(Question.objects.filter(is_active=True))

    if len(questions) < N:
        return render(request, 'questionnaire/error.html', {
            'error': 'Not enough questions available. Please contact the administrator.',
            'medcat_version': medcat_version,
        })


    selected_questions = random.sample(questions, N)

    # Format questions for response
    questions_data = []
    for q in selected_questions:
        questions_data.append({
            'id': q.id,
            'question': q.question_text,
            'options': {
                'a': q.option_a,
                'b': q.option_b,
                'c': q.option_c,
                'd': q.option_d,
            }
        })

    return render(request, 'questionnaire/quiz.html', {
        'questions': selected_questions,
        'total': N,
        'medcat_version': medcat_version,
    })



@csrf_exempt
@require_http_methods(["POST"])
def submit_questionnaire(request):
    """Validate answers and generate API key if all correct"""
    identifier = get_client_identifier(request)

    # Check if user can attempt
    if not UserAttempt.can_attempt(identifier):
        cooldown = UserAttempt.get_cooldown_remaining(identifier)
        return JsonResponse({
            'error': 'Too many failed attempts',
            'cooldown_seconds': cooldown
        }, status=429)

    try:
        data = json.loads(request.body)
        answers = data.get('answers', {})  # Expected format: {"question_id": "a", ...}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not answers:
        return JsonResponse({'error': 'No answers provided'}, status=400)

    # Validate all answers
    all_correct = True
    for question_id, user_answer in answers.items():
        try:
            question = Question.objects.get(id=question_id, is_active=True)
            if question.correct_answer != user_answer.lower():
                all_correct = False
                break
        except Question.DoesNotExist:
            return JsonResponse({
                'error': f'Invalid question ID: {question_id}'
            }, status=400)

    # Record attempt
    with transaction.atomic():
        attempt = UserAttempt.objects.create(
            identifier=identifier,
            passed=all_correct
        )

        if all_correct:
            # Generate API key
            api_key = APIKey.objects.create(identifier=identifier)
            
            # Build the full URL to the secret endpoint
            scheme = 'https' if request.is_secure() else 'http'
            host = request.get_host()
            secret_url = f"{scheme}://{host}/callback-after-questionnaire/?api_key={api_key.key}"

            return JsonResponse({
                'success': True,
                'message': 'All answers correct! API key generated.',
                'api_key': api_key.key,
                'expires_at': api_key.expires_at.isoformat(),
                'valid_for_minutes': cooldown_minutes,
                'secret_link': secret_url
            })

        else:
            return JsonResponse({
                'success': False,
                'message': 'Some answers were incorrect. '
                f'Try again in {cooldown_minutes} minutes.',
                'cooldown_seconds': cooldown_minutes * 60,
            }, status=403)


# Optional: Endpoint to check API key validity
@csrf_exempt
@require_http_methods(["GET"])
def check_api_key(request):
    """Check if an API key is valid"""
    api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')

    if not api_key:
        return JsonResponse({'error': 'No API key provided'}, status=400)

    is_valid = APIKey.is_valid(api_key)

    if is_valid:
        key_obj = APIKey.objects.get(key=api_key)
        return JsonResponse({
            'valid': True,
            'expires_at': key_obj.expires_at.isoformat()
        })
    else:
        return JsonResponse({
            'valid': False,
            'message': 'API key is invalid or expired'
        }, status=401)
