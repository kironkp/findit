import json
from concurrent.futures import ThreadPoolExecutor

from django.core.files.base import ContentFile
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from .forms import ItemForm, LocationForm, MoveForm
from .icons import ICON_SLUGS, LOCATION_ICONS, suggest_icon
from .models import Item, Location, LocationLog, Tag
from .services.bulk_intake import parse_items, transcribe
from .services.image_search import fetch_first_image

STARTER_LOCATIONS = ['Kitchen', 'Bedroom', 'Living Room', 'Garage']


@ensure_csrf_cookie
def home(request):
    if request.user.is_authenticated:
        items = list(
            Item.objects.filter(user=request.user, archived=False)
            .select_related('location')
            .order_by('name')
        )
        locations = list(
            Location.objects.filter(user=request.user)
            .select_related('parent')
            .order_by('name')
        )
        by_id = {loc.id: loc for loc in locations}
        for loc in locations:
            loc.children_list = []
            loc.items_list = []
        for item in items:
            if item.location_id and item.location_id in by_id:
                by_id[item.location_id].items_list.append(item)
        roots = []
        for loc in locations:
            if loc.parent_id and loc.parent_id in by_id:
                by_id[loc.parent_id].children_list.append(loc)
            else:
                roots.append(loc)
        orphan_items = [i for i in items if not i.location_id]

        recent_moves = (
            LocationLog.objects
            .filter(item__user=request.user)
            .select_related('item', 'location')[:5]
        )

        # All currently-lent items (regardless of return date), each tagged with
        # the most recent lend log so we can show return_by + note + overdue flag.
        from datetime import date as _date
        today = timezone.now().date()
        lent_items = list(
            Item.objects
            .filter(user=request.user, archived=False, location__is_person=True)
            .select_related('location')
        )
        lent_info = []
        for it in lent_items:
            last_log = (
                it.location_logs.filter(location=it.location)
                .order_by('-moved_at').first()
            )
            return_by = last_log.return_by if last_log else None
            lent_info.append({
                'item': it,
                'location': it.location,
                'return_by': return_by,
                'note': last_log.note if last_log else '',
                'overdue': bool(return_by and return_by < today),
            })
        # Sort: overdue first (most overdue), then upcoming by date, then name.
        lent_info.sort(key=lambda x: (
            not x['overdue'],
            x['return_by'] or _date.max,
            x['item'].name.lower(),
        ))

        context = {
            'item_count': len(items),
            'location_count': len(locations),
            'collection_tree': roots,
            'orphan_items': orphan_items,
            'recent_moves': recent_moves,
            'lent_info': lent_info,
        }
        return render(request, 'home.html', context)
    return render(request, 'home.html')


def about(request):
    return render(request, 'about.html')


def signup(request):
    error_message = ''
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            for name in STARTER_LOCATIONS:
                Location.objects.create(user=user, name=name)
            login(request, user)
            return redirect('item-index')
        error_message = 'Invalid sign up - try again'
    form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form, 'error': error_message})


# ---------- Items ----------

@login_required
def item_index(request):
    items = Item.objects.filter(user=request.user).select_related('location')
    show_archived = request.GET.get('archived') == '1'
    if not show_archived:
        items = items.filter(archived=False)
    query = request.GET.get('q', '').strip()
    if query:
        items = items.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(distinguishing_detail__icontains=query)
            | Q(tags__name__icontains=query)
        ).distinct()
    tag_id = request.GET.get('tag')
    if tag_id:
        items = items.filter(tags__id=tag_id)
    location_id = request.GET.get('location')
    if location_id:
        items = items.filter(location_id=location_id)
    # Default to list view (formerly defaulted to cards).
    view_mode = 'cards' if request.GET.get('view') == 'cards' else 'list'

    def qs_with(view):
        qd = request.GET.copy()
        qd['view'] = view
        return qd.urlencode()

    # Build the Locations section: roots with sub-locations, same shape as
    # LocationList used so the existing template partial still works.
    user_locations = list(
        Location.objects.filter(user=request.user).select_related('parent')
    )
    by_id = {loc.id: loc for loc in user_locations}
    for loc in user_locations:
        loc.children_list = []
    location_roots = []
    people_roots = []
    for loc in user_locations:
        if loc.parent_id and loc.parent_id in by_id:
            by_id[loc.parent_id].children_list.append(loc)
        elif loc.is_person:
            people_roots.append(loc)
        else:
            location_roots.append(loc)
    location_roots.sort(key=lambda l: l.name.lower())
    people_roots.sort(key=lambda l: l.name.lower())
    for loc in user_locations:
        loc.children_list.sort(key=lambda l: l.name.lower())

    context = {
        'items': items,
        'query': query,
        'show_archived': show_archived,
        'selected_tag': int(tag_id) if tag_id else None,
        'selected_location': int(location_id) if location_id else None,
        'tags': Tag.objects.all(),
        'locations': user_locations,
        'root_groups': location_roots,   # backward-compat for any other template using this
        'location_roots': location_roots,
        'people_roots': people_roots,
        'no_match_query': query if query and not items.exists() else '',
        'view_mode': view_mode,
        'qs_cards': qs_with('cards'),
        'qs_list': qs_with('list'),
    }
    return render(request, 'items/index.html', context)


@login_required
def item_detail(request, pk):
    item = get_object_or_404(Item, pk=pk, user=request.user)
    move_form = MoveForm(user=request.user)
    available_tags = Tag.objects.exclude(id__in=item.tags.values_list('id'))
    history = item.location_logs.select_related('location')
    known_people = (
        Location.objects.filter(user=request.user, is_person=True).order_by('name')
    )
    is_lent = bool(item.location and item.location.is_person)
    # Find the most recent lend log so we can show the original return-by date.
    current_lend = None
    if is_lent:
        current_lend = (
            item.location_logs.filter(location=item.location)
            .order_by('-moved_at').first()
        )
    context = {
        'item': item,
        'move_form': move_form,
        'available_tags': available_tags,
        'history': history,
        'known_people': known_people,
        'is_lent': is_lent,
        'current_lend': current_lend,
    }
    return render(request, 'items/detail.html', context)


class ItemCreate(LoginRequiredMixin, CreateView):
    model = Item
    form_class = ItemForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        prefill = self.request.GET.get('name')
        if prefill:
            initial['name'] = prefill
        location_id = self.request.GET.get('location')
        if location_id:
            if Location.objects.filter(pk=location_id, user=self.request.user).exists():
                initial['location'] = location_id
        return initial

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        if form.instance.location:
            LocationLog.objects.create(
                item=form.instance,
                location=form.instance.location,
                note='Initial location',
            )
        return response


class ItemUpdate(LoginRequiredMixin, UpdateView):
    model = Item
    form_class = ItemForm

    def get_queryset(self):
        return Item.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class ItemDelete(LoginRequiredMixin, DeleteView):
    model = Item
    success_url = reverse_lazy('item-index')

    def get_queryset(self):
        return Item.objects.filter(user=self.request.user)


# ---------- Bulk add (dictation → AI parse → preview → save) ----------

@login_required
def bulk_item_form(request):
    from django.conf import settings
    locations = list(
        Location.objects.filter(user=request.user)
        .select_related('parent')
        .order_by('name')
    )
    ctx = {
        'locations': locations,
        'ai_enabled': bool(getattr(settings, 'OPENAI_API_KEY', '')),
    }
    return render(request, 'items/bulk.html', ctx)


@login_required
@require_POST
def bulk_transcribe(request):
    import logging
    log = logging.getLogger(__name__)
    audio = request.FILES.get('audio')
    if not audio:
        return JsonResponse({'error': 'No audio uploaded'}, status=400)
    size = getattr(audio, 'size', 0)
    name = getattr(audio, 'name', 'audio.webm')
    log.info('Whisper upload: name=%s size=%s bytes content_type=%s',
             name, size, getattr(audio, 'content_type', '?'))
    text = transcribe(audio, filename=name)
    if text is None:
        return JsonResponse({'error': 'Transcription failed — check OPENAI_API_KEY and try again.'}, status=502)
    log.info('Whisper result: %d chars from %s bytes', len(text), size)
    return JsonResponse({'transcript': text, 'audio_bytes': size})


@login_required
@require_POST
def bulk_parse(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    text = (payload.get('text') or '').strip()
    if not text:
        return JsonResponse({'error': 'No text to parse'}, status=400)

    locations = list(
        Location.objects.filter(user=request.user)
        .select_related('parent')
        .order_by('name')
    )

    def path_for(loc):
        parts = []
        cur = loc
        seen = set()
        while cur and cur.id not in seen:
            seen.add(cur.id)
            parts.append(cur.name)
            cur = cur.parent
        return ' > '.join(reversed(parts))

    paths = {loc.id: path_for(loc) for loc in locations}
    parsed = parse_items(text, paths.values(), icon_slugs=ICON_SLUGS)
    if not parsed:
        return JsonResponse({'items': [], 'note': 'No items extracted — try rephrasing.'})

    # Match suggestion in priority order: exact path → leaf name (last segment) → no match.
    path_to_id = {p.lower(): lid for lid, p in paths.items()}
    leaf_to_id = {loc.name.lower(): loc.id for loc in locations}
    for item in parsed:
        sugg = item['location_suggestion']
        if not sugg:
            item['matched_location_id'] = None
            item['new_location_name'] = ''
            continue
        key = sugg.lower()
        if key in path_to_id:
            item['matched_location_id'] = path_to_id[key]
            item['new_location_name'] = ''
            continue
        # Try matching just the leaf (last segment) if user used a partial path.
        leaf = sugg.split('>')[-1].strip().lower()
        if leaf and leaf == key and leaf in leaf_to_id:
            item['matched_location_id'] = leaf_to_id[leaf]
            item['new_location_name'] = ''
        else:
            item['matched_location_id'] = None
            item['new_location_name'] = sugg
    return JsonResponse({'items': parsed})


@login_required
@require_POST
@transaction.atomic
def bulk_save(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    rows = payload.get('items') if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        return JsonResponse({'error': 'No items to save'}, status=400)

    user = request.user
    location_cache = {
        loc.id: loc for loc in Location.objects.filter(user=user).select_related('parent')
    }
    # Map (parent_id, lowered_name) → Location for sibling lookup at each path segment.
    sibling_index = {(loc.parent_id, loc.name.lower()): loc for loc in location_cache.values()}

    def resolve_path(path_str, icon_map):
        """Walk 'A > B > C', creating any missing segments under the correct parent.
        `icon_map` maps each segment name to an AI-suggested icon slug (or {}).
        """
        nonlocal created_locations
        parts = [p.strip() for p in path_str.split('>') if p.strip()]
        parent_id = None
        leaf = None
        for part in parts:
            key = (parent_id, part.lower())
            existing = sibling_index.get(key)
            if existing:
                leaf = existing
                parent_id = existing.id
                continue
            hinted = (icon_map.get(part) or '').strip() if isinstance(icon_map, dict) else ''
            icon = hinted if hinted in ICON_SLUGS else (suggest_icon(part) or '')
            new_loc = Location.objects.create(
                user=user,
                parent_id=parent_id,
                name=part[:100],
                icon=icon,
            )
            location_cache[new_loc.id] = new_loc
            sibling_index[(parent_id, part.lower())] = new_loc
            created_locations += 1
            leaf = new_loc
            parent_id = new_loc.id
        return leaf

    created_items = 0
    created_locations = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = (row.get('name') or '').strip()[:100]
        if not name:
            continue
        detail = (row.get('distinguishing_detail') or '').strip()[:200]
        try:
            qty = max(1, int(row.get('quantity') or 1))
        except (TypeError, ValueError):
            qty = 1

        location = None
        loc_kind = row.get('location_kind')  # 'existing' | 'new' | 'none'
        if loc_kind == 'existing':
            try:
                loc_id = int(row.get('location_id') or 0)
            except (TypeError, ValueError):
                loc_id = 0
            location = location_cache.get(loc_id)
            if location and location.user_id != user.id:
                location = None
        elif loc_kind == 'new':
            new_name = (row.get('new_location_name') or '').strip()
            if new_name:
                icon_map = row.get('new_location_icons') or {}
                if not isinstance(icon_map, dict):
                    icon_map = {}
                location = resolve_path(new_name, icon_map)

        item = Item.objects.create(
            user=user,
            name=name,
            distinguishing_detail=detail,
            quantity=qty,
            location=location,
        )
        if location:
            LocationLog.objects.create(
                item=item, location=location, note='Bulk add'
            )
        created_items += 1

    # Fetch product images for every newly-created item in parallel.
    # Whisper + parse already took a few seconds; image fetch is the slow part.
    created_qs = Item.objects.filter(
        user=user, photo='',
    ).order_by('-id')[:len(rows)]
    new_items = list(created_qs)

    def _fetch_one(item):
        query = item.name
        if item.distinguishing_detail:
            query = f'{query} {item.distinguishing_detail}'
        return item, fetch_first_image(query)

    images_attached = 0
    if new_items:
        with ThreadPoolExecutor(max_workers=6) as ex:
            for item, result in ex.map(_fetch_one, new_items):
                if not result:
                    continue
                filename, data = result
                item.photo.save(filename, ContentFile(data), save=True)
                images_attached += 1

    return JsonResponse({
        'ok': True,
        'created_items': created_items,
        'created_locations': created_locations,
        'images_attached': images_attached,
        'redirect': reverse('item-index'),
    })


@login_required
@require_POST
def lend_item(request, pk):
    """Lend an item to a person — finds-or-creates a person Location and moves the item."""
    item = get_object_or_404(Item, pk=pk, user=request.user)
    person_name = (request.POST.get('person_name') or '').strip()[:100]
    if not person_name:
        messages.error(request, 'Add a name to lend it out.')
        return redirect('item-detail', pk=item.pk)
    return_by = (request.POST.get('return_by') or '').strip() or None

    person = (
        Location.objects
        .filter(user=request.user, name__iexact=person_name)
        .first()
    )
    if person is None:
        person = Location.objects.create(
            user=request.user, name=person_name, is_person=True, icon='user',
        )
    elif not person.is_person:
        # Existing location with same name — promote it to a person so the
        # lending semantics work, but warn the user.
        person.is_person = True
        if not person.icon:
            person.icon = 'user'
        person.save(update_fields=['is_person', 'icon'])

    item.location = person
    item.last_confirmed = timezone.now()
    item.save(update_fields=['location', 'last_confirmed'])
    LocationLog.objects.create(
        item=item, location=person,
        note=f'Lent to {person_name}',
        return_by=return_by or None,
    )
    return redirect('item-detail', pk=item.pk)


@login_required
@require_POST
def return_item(request, pk):
    """Mark a lent item as returned. Moves it back to the most recent non-person
    location in its history; if there isn't one, clears the location."""
    item = get_object_or_404(Item, pk=pk, user=request.user)
    prev = (
        item.location_logs
        .filter(location__isnull=False, location__is_person=False)
        .select_related('location')
        .first()  # ordering is -moved_at on the model
    )
    new_loc = prev.location if prev else None
    item.location = new_loc
    item.last_confirmed = timezone.now()
    item.save(update_fields=['location', 'last_confirmed'])
    LocationLog.objects.create(
        item=item, location=new_loc, note='Returned',
    )
    return redirect('item-detail', pk=item.pk)


@login_required
def move_item(request, pk):
    item = get_object_or_404(Item, pk=pk, user=request.user)
    if request.method == 'POST':
        form = MoveForm(request.POST, user=request.user)
        if form.is_valid():
            log = form.save(commit=False)
            log.item = item
            log.save()
            item.location = log.location
            item.last_confirmed = timezone.now()
            item.save(update_fields=['location', 'last_confirmed'])
    return redirect('item-detail', pk=item.pk)


class LocationLogUpdate(LoginRequiredMixin, UpdateView):
    model = LocationLog
    form_class = MoveForm
    template_name = 'main_app/locationlog_form.html'

    def get_queryset(self):
        return LocationLog.objects.filter(item__user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('item-detail', kwargs={'pk': self.object.item_id})


class LocationLogDelete(LoginRequiredMixin, DeleteView):
    model = LocationLog
    template_name = 'main_app/locationlog_confirm_delete.html'

    def get_queryset(self):
        return LocationLog.objects.filter(item__user=self.request.user)

    def get_success_url(self):
        return reverse('item-detail', kwargs={'pk': self.object.item_id})


@login_required
@require_POST
def quick_move_item(request, pk):
    item = get_object_or_404(Item, pk=pk, user=request.user)
    loc_id = request.POST.get('location_id')
    location = get_object_or_404(Location, pk=loc_id, user=request.user)
    LocationLog.objects.create(item=item, location=location, note='Moved via map')
    item.location = location
    item.last_confirmed = timezone.now()
    item.save(update_fields=['location', 'last_confirmed'])
    return HttpResponse(status=204)


@login_required
def confirm_item(request, pk):
    item = get_object_or_404(Item, pk=pk, user=request.user)
    if request.method == 'POST':
        item.last_confirmed = timezone.now()
        item.save(update_fields=['last_confirmed'])
    return redirect('item-detail', pk=item.pk)


@login_required
def archive_item(request, pk):
    item = get_object_or_404(Item, pk=pk, user=request.user)
    if request.method == 'POST':
        item.archived = not item.archived
        item.save(update_fields=['archived'])
    next_url = request.POST.get('next') or reverse('item-detail', kwargs={'pk': item.pk})
    return HttpResponseRedirect(next_url)


@login_required
def add_tag(request, pk, tag_id):
    item = get_object_or_404(Item, pk=pk, user=request.user)
    tag = get_object_or_404(Tag, pk=tag_id)
    item.tags.add(tag)
    return redirect('item-detail', pk=item.pk)


@login_required
def remove_tag(request, pk, tag_id):
    item = get_object_or_404(Item, pk=pk, user=request.user)
    tag = get_object_or_404(Tag, pk=tag_id)
    item.tags.remove(tag)
    return redirect('item-detail', pk=item.pk)


# ---------- Locations ----------

class LocationList(LoginRequiredMixin, ListView):
    model = Location
    context_object_name = 'locations'

    def get_queryset(self):
        return Location.objects.filter(user=self.request.user).select_related('parent')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        locations = list(ctx['locations'])
        by_id = {loc.id: loc for loc in locations}
        for loc in locations:
            loc.children_list = []
        roots = []
        for loc in locations:
            if loc.parent_id and loc.parent_id in by_id:
                by_id[loc.parent_id].children_list.append(loc)
            else:
                roots.append(loc)
        roots.sort(key=lambda l: l.name.lower())
        for loc in locations:
            loc.children_list.sort(key=lambda l: l.name.lower())
        ctx['root_groups'] = roots
        return ctx


@login_required
@ensure_csrf_cookie
def location_map(request):
    locations = list(
        Location.objects.filter(user=request.user).select_related('parent').order_by('name')
    )
    by_id = {loc.id: loc for loc in locations}
    for loc in locations:
        loc.children_list = []
    location_roots = []
    people_roots = []
    for loc in locations:
        if loc.parent_id and loc.parent_id in by_id:
            by_id[loc.parent_id].children_list.append(loc)
        elif loc.is_person:
            people_roots.append(loc)
        else:
            location_roots.append(loc)
    return render(request, 'main_app/location_map.html', {
        'location_roots': location_roots,
        'people_roots': people_roots,
    })


@login_required
@require_POST
def location_reparent(request, pk):
    """Change a location's parent. Used by the home tree drag-and-drop."""
    location = get_object_or_404(Location, pk=pk, user=request.user)
    parent_id_raw = request.POST.get('parent_id')
    new_parent = None
    if parent_id_raw and parent_id_raw not in ('', 'null', 'none'):
        try:
            new_parent = Location.objects.get(pk=int(parent_id_raw), user=request.user)
        except (Location.DoesNotExist, ValueError, TypeError):
            return JsonResponse({'error': 'Parent not found'}, status=404)
        if new_parent.id == location.id:
            return JsonResponse({'error': "Can't be its own parent"}, status=400)
        # Walk up from new_parent to root; if we hit `location`, the move would
        # create a cycle (dropping a parent into one of its own descendants).
        cur = new_parent
        seen = set()
        while cur:
            if cur.id == location.id:
                return JsonResponse({'error': "Can't move a location into its own descendant"}, status=400)
            if cur.id in seen:
                break
            seen.add(cur.id)
            cur = cur.parent
    location.parent = new_parent
    location.save(update_fields=['parent'])
    return JsonResponse({'ok': True})


@login_required
def location_panel(request, pk):
    location = get_object_or_404(Location, pk=pk, user=request.user)
    children = location.children.order_by('name')
    items = location.items.filter(archived=False)
    return render(
        request,
        'main_app/_location_panel.html',
        {'location': location, 'children': children, 'items': items},
    )


class LocationDetail(LoginRequiredMixin, DetailView):
    model = Location
    context_object_name = 'location'

    def get_queryset(self):
        return Location.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.filter(archived=False)
        ctx['children'] = self.object.children.all()
        return ctx


class LocationCreate(LoginRequiredMixin, CreateView):
    model = Location
    form_class = LocationForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        parent_id = self.request.GET.get('parent')
        if parent_id and parent_id.isdigit():
            parent = Location.objects.filter(pk=parent_id, user=self.request.user).first()
            if parent:
                initial['parent'] = parent
        return initial

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        if self.object.parent_id:
            return reverse('location-map')
        return reverse('location-index')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['icon_catalog'] = LOCATION_ICONS

        return ctx


class LocationUpdate(LoginRequiredMixin, UpdateView):
    model = Location
    form_class = LocationForm
    success_url = reverse_lazy('location-index')

    def get_queryset(self):
        return Location.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['icon_catalog'] = LOCATION_ICONS

        return ctx


class LocationDelete(LoginRequiredMixin, DeleteView):
    model = Location
    success_url = reverse_lazy('location-index')

    def get_queryset(self):
        return Location.objects.filter(user=self.request.user)


# ---------- Tags (shared catalog) ----------

class TagList(LoginRequiredMixin, ListView):
    model = Tag
    context_object_name = 'tags'


class TagDetail(LoginRequiredMixin, DetailView):
    model = Tag
    context_object_name = 'tag'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.filter(user=self.request.user, archived=False)
        return ctx


class TagCreate(LoginRequiredMixin, CreateView):
    model = Tag
    fields = ['name', 'color']
    success_url = reverse_lazy('tag-index')


class TagUpdate(LoginRequiredMixin, UpdateView):
    model = Tag
    fields = ['name', 'color']
    success_url = reverse_lazy('tag-index')


class TagDelete(LoginRequiredMixin, DeleteView):
    model = Tag
    success_url = reverse_lazy('tag-index')
