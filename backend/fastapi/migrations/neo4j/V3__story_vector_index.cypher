// Story 대표벡터(centroid) 유사도 기반 Event->Story 편입 판단용 벡터 인덱스
// 차원: nlpai-lab/KURE-v1 (1024-d, Event embedding과 동일). 모델·차원이 바뀌면 DROP 후 재생성.
CREATE VECTOR INDEX story_embedding_index IF NOT EXISTS
FOR (s:Story)
ON (s.embedding)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1024,
        `vector.similarity_function`: 'cosine'
    }
};
