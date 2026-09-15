// Event 콘텐츠 기반 추천(CBF)/중복 판단용 벡터 인덱스
// 차원: nlpai-lab/KURE-v1 (1024-d). 모델·차원이 바뀌면 DROP 후 재생성.
CREATE VECTOR INDEX event_embedding_index IF NOT EXISTS
FOR (e:Event)
ON (e.embedding)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1024,
        `vector.similarity_function`: 'cosine'
    }
};
