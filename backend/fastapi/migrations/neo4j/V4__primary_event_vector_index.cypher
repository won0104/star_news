// 적어도 한 기사에서 메인 주제(COVERS.isPrimary=true) Event만 모은 서브셋.
// CBF 벡터 검색이 이 라벨 대상 인덱스를 쓰면, 부수적으로만 언급된 Event가 후보에 섞이지 않는다.
// 차원: nlpai-lab/KURE-v1 (1024-d). event_embedding_index와 동일 설정.
CREATE VECTOR INDEX primary_event_embedding_index IF NOT EXISTS
FOR (e:PrimaryEvent)
ON (e.embedding)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1024,
        `vector.similarity_function`: 'cosine'
    }
};

// 기존 데이터 백필 - 이미 isPrimary=true COVERS를 가진 Event에 라벨을 붙인다
// 앞으로 새로 생기는 Event는 merge_covers_edge가 isPrimary=true를 처음 세팅하는 순간 라벨을 붙인다
MATCH (e:Event)
WHERE EXISTS { (:Article)-[c:COVERS]->(e) WHERE c.isPrimary = true }
SET e:PrimaryEvent;
