
SELECT 
    s.name AS suspect_name,
    s.relationship_to_victim,
    s.motive,
    a.alibi,
    a.alibi_verified,
    a.alibi_time
FROM 
    Suspects s
LEFT JOIN 
    Alibis a ON s.suspect_id = a.suspect_id;

SELECT 
    cs.location AS crime_scene_location,
    cs.description AS crime_scene_description,
    v.name AS victim_name,
    v.time_of_death,
    e.description AS evidence_description,
    e.found_at_location
FROM 
    CrimeScene cs
JOIN 
    Victim v ON cs.victim_id = v.victim_id
LEFT JOIN 
    Evidence e ON cs.scene_id = e.scene_id;


SELECT 
    s.name AS suspect_name,
    a.alibi,
    a.alibi_verified,
    e.description AS evidence_description,
    e.found_at_location
FROM 
    Suspects s
JOIN 
    Alibis a ON s.suspect_id = a.suspect_id
LEFT JOIN 
    Evidence e ON s.suspect_id = e.points_to_suspect_id
WHERE 
    a.alibi_verified = TRUE;


SELECT 
    e.evidence_id,
    e.description AS evidence_description,
    e.found_at_location,
    cs.location AS crime_scene_location
FROM 
    Evidence e
LEFT JOIN 
    Suspects s ON e.points_to_suspect_id = s.suspect_id
JOIN 
    CrimeScene cs ON e.scene_id = cs.scene_id
WHERE 
    e.points_to_suspect_id IS NULL;

