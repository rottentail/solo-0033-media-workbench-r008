"""Allocate a shared byte budget to complete offline projects, not single clips."""


def choose(projects, sizes, capacity):
    if type(capacity) is not int or capacity < 0:
        raise ValueError('media capacity must be a nonnegative integer')
    if len(projects) > 16:
        raise ValueError('at most sixteen candidate projects are supported')
    if any(type(n) is not int or n <= 0 for n in sizes.values()):
        raise ValueError('rendition sizes must be positive integers')
    identities = [p['id'] for p in projects]
    if len(set(identities)) != len(identities):
        raise ValueError('candidate projects must be unique')
    required = [frozenset(p['required']) for p in projects]
    if any(not group or not group <= sizes.keys() for group in required):
        raise ValueError('every project requires available media')
    if any(type(p['priority']) is not int or p['priority'] <= 0 for p in projects):
        raise ValueError('project priorities must be positive integers')
    # Every useful package is the union of one or more whole projects. Shared
    # renditions consume bytes once; selecting them can complete other projects.
    unions = {frozenset(): 0}
    for group in required:
        for previous, cost in list(unions.items()):
            combined = previous | group
            if combined not in unions:
                total = cost + sum(sizes[key] for key in group - previous)
                if total <= capacity:
                    unions[combined] = total
    best = (0, 0, (), ())
    for media, cost in unions.items():
        covered = tuple(sorted(p['id'] for p, group in zip(projects, required) if group <= media))
        value = sum(p['priority'] for p in projects if p['id'] in covered)
        candidate = (-value, cost, covered, tuple(sorted(media)))
        if candidate < best:
            best = candidate
    return {'project_ids': list(best[2]), 'media': list(best[3]),
            'value': -best[0], 'media_bytes': best[1]}


def distribute(projects, sizes, capacities):
    """Choose independent media unions for each physical offline volume."""
    if (not isinstance(capacities, list) or not 1 <= len(capacities) <= 3
            or any(type(n) is not int or n < 0 for n in capacities)):
        raise ValueError('one to three nonnegative volume capacities required')
    if len(projects) > 12:
        raise ValueError('a volume set supports at most twelve projects')
    choose(projects, sizes, 0)
    # Build one selected media pool, then place its members on the volumes.
    pooled = choose(projects, sizes, sum(capacities))
    placements = [set() for capacity in capacities]
    remaining = list(capacities)
    owners = {}
    ordered = sorted(pooled['media'], key=lambda key: (-sizes[key], key))
    for key in ordered:
        possibilities = [i for i, available in enumerate(remaining) if sizes[key] <= available]
        if not possibilities:
            continue
        volume = max(possibilities, key=lambda i: (remaining[i], -i))
        placements[volume].add(key)
        remaining[volume] -= sizes[key]
        owners[key] = volume
    available = set(owners)
    assignments = {}
    value = 0
    for project in sorted(projects, key=lambda item: item['id']):
        required = set(project['required'])
        if not required <= available:
            continue
        counts = []
        for volume, media in enumerate(placements):
            counts.append((len(required & media), -volume))
        volume = -max(counts)[1]
        assignments[project['id']] = volume
        value += project['priority']
    volumes = []
    for volume, media in enumerate(placements):
        identities = sorted(pid for pid, owner in assignments.items() if owner == volume)
        score = sum(project['priority'] for project in projects if project['id'] in identities)
        volumes.append({'project_ids': identities, 'media': sorted(media),
            'media_bytes': sum(sizes[key] for key in media), 'value': score})
    return {'project_ids': sorted(assignments), 'value': value,
            'media_bytes': sum(sizes[key] for key in available), 'volumes': volumes}
