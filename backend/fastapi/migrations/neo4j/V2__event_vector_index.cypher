// Event 콘텐츠 기반 추천(CBF)/중복 판단용 벡터 인덱스
// 차원(768)·유사도 함수는 임시값. 임베딩 모델 확정되면 재확인 필요.
// 값이 바뀌면: DROP INDEX event_embedding_index; 실행 후 이 파일 값 고쳐서 재실행.
CREATE VECTOR INDEX event_embedding_index IF NOT EXISTS
FOR (e:Event)
ON (e.embedding)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 768,
        `vector.similarity_function`: 'cosine'
    }
};
