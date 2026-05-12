"""Curated Lucide icon catalog + keyword auto-suggest for locations.

Icons are vendored under main_app/static/icons/ and inlined into HTML via the
`location_icon` template tag — `currentColor` handles recoloring, with no
cross-origin or mask-image quirks.
"""


LOCATION_ICONS = [
    # Spaces
    ('house', 'Home'),
    ('building', 'Building'),
    ('door-open', 'Door'),
    ('door-closed', 'Door closed'),
    ('bed', 'Bed'),
    ('sofa', 'Sofa'),
    ('armchair', 'Armchair'),
    ('lamp', 'Lamp'),
    ('utensils', 'Kitchen'),
    ('refrigerator', 'Fridge'),
    ('coffee', 'Coffee'),
    ('wine', 'Wine'),
    ('washing-machine', 'Laundry'),
    ('shower-head', 'Bath'),
    ('droplets', 'Water'),
    ('warehouse', 'Storage'),
    ('tree-pine', 'Outdoor'),
    ('flower', 'Garden'),
    ('car', 'Garage'),
    ('sailboat', 'Sailboat'),
    ('ship', 'Ship'),
    ('anchor', 'Anchor'),
    ('waves', 'Water'),

    # Containers
    ('box', 'Box'),
    ('package', 'Package'),
    ('archive', 'Drawer'),
    ('container', 'Bin'),
    ('briefcase', 'Briefcase'),
    ('backpack', 'Backpack'),
    ('shopping-bag', 'Bag'),
    ('library', 'Shelf'),
    ('folder', 'Folder'),
    ('file', 'File'),
    ('book', 'Book'),
    ('book-open', 'Book open'),

    # Wearables / Items
    ('shirt', 'Clothes'),
    ('glasses', 'Glasses'),
    ('watch', 'Watch'),
    ('gift', 'Gift'),
    ('key', 'Key'),

    # Tech / Studio
    ('laptop', 'Laptop'),
    ('monitor', 'Monitor'),
    ('keyboard', 'Keyboard'),
    ('mouse', 'Mouse'),
    ('camera', 'Camera'),
    ('headphones', 'Headphones'),
    ('mic', 'Mic'),
    ('music', 'Music'),
    ('guitar', 'Guitar'),
    ('speaker', 'Speaker'),
    ('gamepad-2', 'Gamepad'),

    # Tools / Craft
    ('wrench', 'Wrench'),
    ('hammer', 'Hammer'),
    ('paintbrush', 'Paint'),
    ('scissors', 'Scissors'),
    ('ruler', 'Ruler'),
    ('pencil', 'Pencil'),

    # Health
    ('pill', 'Medicine'),
    ('syringe', 'Syringe'),

    # People / Pets
    ('baby', 'Baby'),
    ('dog', 'Dog'),
    ('cat', 'Cat'),
    ('user', 'Person'),
    ('users', 'People'),

    # Generic markers
    ('star', 'Star'),
    ('heart', 'Heart'),
    ('flag', 'Flag'),
    ('bookmark', 'Bookmark'),
    ('tag', 'Tag'),
    ('map-pin', 'Pin'),
    ('hash', 'Hash'),
    ('circle', 'Circle'),
    ('square', 'Square'),
]

ICON_SLUGS = {slug for slug, _ in LOCATION_ICONS}


# Keyword → icon slug. Order matters: longer/more-specific keys first so a
# substring match on "bedroom" wins over "bed". Iterated in insertion order.
KEYWORD_TO_ICON = {
    # rooms / spaces
    'bedroom': 'bed',
    'kitchen': 'utensils',
    'pantry': 'utensils',
    'fridge': 'refrigerator',
    'living': 'sofa',
    'lounge': 'sofa',
    'family room': 'sofa',
    'office': 'briefcase',
    'study': 'book',
    'library': 'library',
    'bathroom': 'shower-head',
    'bath': 'shower-head',
    'laundry': 'washing-machine',
    'garage': 'car',
    'attic': 'warehouse',
    'basement': 'warehouse',
    'storage': 'warehouse',
    'garden': 'flower',
    'yard': 'tree-pine',
    'patio': 'tree-pine',
    'house': 'house',
    'apartment': 'building',
    'studio': 'mic',

    # furniture / surfaces
    'couch': 'sofa',
    'sofa': 'sofa',
    'chair': 'armchair',
    'lamp': 'lamp',
    'desk': 'briefcase',
    'bookshelf': 'library',
    'shelf': 'library',
    'closet': 'shirt',
    'wardrobe': 'shirt',
    'dresser': 'shirt',
    'cabinet': 'archive',
    'drawer': 'archive',

    # containers
    'box': 'box',
    'crate': 'box',
    'bin': 'container',
    'container': 'container',
    'bag': 'shopping-bag',
    'backpack': 'backpack',
    'briefcase': 'briefcase',
    'folder': 'folder',
    'binder': 'folder',
    'file': 'file',

    # items
    'clothes': 'shirt',
    'clothing': 'shirt',
    'shirt': 'shirt',
    'shoe': 'shirt',
    'jewelry': 'gift',
    'glasses': 'glasses',
    'watch': 'watch',
    'key': 'key',
    'gift': 'gift',
    'book': 'book',

    # boat / water
    'sailboat': 'sailboat',
    'boat': 'sailboat',
    'yacht': 'sailboat',
    'ship': 'ship',
    'marina': 'anchor',
    'dock': 'anchor',
    'cockpit': 'sailboat',
    'locker': 'box',

    # tech / studio
    'computer': 'laptop',
    'laptop': 'laptop',
    'monitor': 'monitor',
    'screen': 'monitor',
    'camera': 'camera',
    'music': 'music',
    'guitar': 'guitar',
    'speaker': 'speaker',
    'microphone': 'mic',
    'mic': 'mic',
    'audio': 'speaker',
    'recording': 'mic',
    'gaming': 'gamepad-2',
    'game': 'gamepad-2',

    # tools / craft
    'tool': 'wrench',
    'workshop': 'wrench',
    'paint': 'paintbrush',

    # health
    'medicine': 'pill',
    'medical': 'pill',
    'pill': 'pill',

    # people / pets
    'baby': 'baby',
    'kids': 'baby',
    'child': 'baby',
    'nursery': 'baby',
    'dog': 'dog',
    'cat': 'cat',
    'pet': 'dog',

    # outdoor
    'outdoor': 'tree-pine',
    'shed': 'warehouse',

    # food / drink
    'coffee': 'coffee',
    'wine': 'wine',
    'bar': 'wine',

    # bed
    'bed': 'bed',
}

DEFAULT_ICON = 'map-pin'


def suggest_icon(name):
    """Return a best-guess icon slug for a location name, or None if no match."""
    n = (name or '').strip().lower()
    if not n:
        return None
    for keyword, slug in KEYWORD_TO_ICON.items():
        if keyword in n:
            return slug
    return None
