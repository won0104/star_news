# Code Convention

본 문서는 프로젝트의 코드 품질과 협업 효율을 높이기 위한 공통 코드 컨벤션입니다.

## Tech Stack

| 구분 | 기술 |
| --- | --- |
| Frontend | React |
| Backend | Spring Boot, FastAPI |
| Database | Neo4j, MySQL |
| Infra | Jenkins, Docker, Nginx |

---

# 1. 공통 Convention

## 1.1 기본 원칙

- 코드는 **가독성, 일관성, 유지보수성**을 우선합니다.
- 하나의 함수/메서드는 가능한 한 **하나의 역할만 수행**합니다.
- 중복 코드는 공통 함수, 컴포넌트, 모듈로 분리합니다.
- 의미 없는 축약어 사용을 지양합니다.
- 매직 넘버와 하드코딩된 문자열은 상수 또는 환경 변수로 관리합니다.
- 주석은 코드 자체로 설명하기 어려운 **의도와 이유**를 중심으로 작성합니다.
- 사용하지 않는 코드, import, 변수는 바로 제거합니다.
- 비밀키, 비밀번호, API Key 등 민감 정보는 Git에 커밋하지 않습니다.

## 1.2 Naming

| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| 변수 | camelCase | `userName`, `articleList` |
| 함수/메서드 | camelCase, 동사로 시작 | `getUser()`, `createArticle()` |
| 상수 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| 클래스 | PascalCase | `ArticleService` |
| Boolean | `is`, `has`, `can`, `should` 권장 | `isActive`, `hasPermission` |

## 1.3 Git 관련

### Branch Naming

```text
main
dev

<담당영역>/<작업종류>/<Story 번호>-<설명>
```

예시:

```text
be/feat/23-login
fe/feat/24-login-page
ai/feat/25-event-clustering
infra/chore/26-dev-setting
```

### Commit Message

```text
<type>: <내용>
```

| Type | 설명 |
| --- | --- |
| feat | 새로운 기능 |
| fix | 버그 수정 |
| refactor | 코드 개선 |
| docs | 문서 수정 |
| test | 테스트 코드 |
| chore | 빌드, 패키지, 설정 변경 |

---

# 2. Frontend - React

## 2.1 Naming Convention

| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| 컴포넌트 | PascalCase | `ArticleCard.jsx` |
| 페이지 | PascalCase | `ArticleDetailPage.jsx` |
| 함수 | camelCase | `handleArticleClick()` |
| 변수 | camelCase | `articleList` |
| 상수 | UPPER_SNAKE_CASE | `DEFAULT_PAGE_SIZE` |
| Custom Hook | `use` + PascalCase/camelCase | `useAuth`, `useArticleList` |

## 2.2 파일 및 폴더 구조

```text
src/
├── api/
├── assets/
├── components/
│   ├── common/
│   └── article/
├── hooks/
├── pages/
├── routes/
├── store/
├── styles/
├── utils/
└── App.jsx
```

- `components`: 재사용 가능한 UI 컴포넌트
- `pages`: 라우팅되는 페이지 단위 컴포넌트
- `api`: API 요청 관련 코드
- `hooks`: Custom Hook
- `store`: 전역 상태 관리
- `utils`: 공통 유틸 함수

## 2.3 Component 작성

- 컴포넌트는 가능한 한 하나의 책임만 가집니다.
- 동일 UI/로직이 반복되면 공통 컴포넌트로 분리합니다.
- 이벤트 함수는 `handle` 접두사를 사용합니다.
- props는 의미가 명확한 이름을 사용합니다.
- 지나치게 큰 컴포넌트는 하위 컴포넌트 또는 Hook으로 분리합니다.

```jsx
function ArticleCard({ article, onSelect }) {
  const handleClick = () => {
    onSelect(article.id);
  };

  return (
    <article onClick={handleClick}>
      <h2>{article.title}</h2>
    </article>
  );
}

export default ArticleCard;
```

## 2.4 API 요청

API 호출 코드는 컴포넌트 내부에 직접 작성하지 않고 `api` 디렉터리로 분리합니다.

```javascript
// api/articleApi.js

export const getArticles = async () => {
  const response = await api.get("/articles");
  return response.data;
};
```

## 2.5 State

- 지역 상태로 해결 가능한 값은 전역 상태로 관리하지 않습니다.
- 서버 데이터와 UI 상태를 구분합니다.
- 파생 가능한 값은 별도 state로 중복 저장하지 않습니다.

```javascript
const [articles, setArticles] = useState([]);
const [isLoading, setIsLoading] = useState(false);
```

## 2.6 Boolean Naming

```javascript
isLoading
isLoggedIn
hasNextPage
canEdit
```

---

# 3. Backend - Spring Boot

## 3.1 Naming Convention

| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| Class | PascalCase | `ArticleService` |
| Method | camelCase | `findArticleById()` |
| Variable | camelCase | `articleList` |
| Constant | UPPER_SNAKE_CASE | `DEFAULT_PAGE_SIZE` |
| Package | lowercase | `com.project.article` |

## 3.2 Package Structure

도메인 중심 구조를 권장합니다.

```text
com.project
├── article
│   ├── controller
│   ├── service
│   ├── repository
│   ├── domain
│   └── dto
├── user
├── recommendation
├── global
│   ├── config
│   ├── error
│   └── response
└── auth
```

## 3.3 Layer 역할

### Controller

- HTTP 요청/응답 처리
- 요청값 검증
- Service 호출
- 비즈니스 로직 작성 금지

```java
@GetMapping("/{articleId}")
public ResponseEntity<ArticleResponse> getArticle(
        @PathVariable Long articleId
) {
    return ResponseEntity.ok(articleService.getArticle(articleId));
}
```

### Service

- 핵심 비즈니스 로직 담당
- Repository를 통해 데이터 접근
- 트랜잭션 처리

```java
@Transactional(readOnly = true)
public ArticleResponse getArticle(Long articleId) {
    Article article = articleRepository.findById(articleId)
            .orElseThrow(() -> new ArticleNotFoundException(articleId));

    return ArticleResponse.from(article);
}
```

### Repository

- 데이터 조회 및 저장 담당
- 비즈니스 로직 작성 지양

## 3.4 DTO

Entity를 API Response에 직접 반환하지 않습니다.

```text
ArticleCreateRequest
ArticleUpdateRequest
ArticleResponse
ArticleSummaryResponse
```

Request와 Response DTO를 명확하게 분리합니다.

## 3.5 Method Naming

```text
getArticle
getArticles
createArticle
updateArticle
deleteArticle

findById
findByUserId
existsByEmail
```

## 3.6 Exception

- 예외 처리는 `GlobalExceptionHandler`에서 공통 처리합니다.
- 단순 `RuntimeException` 대신 의미 있는 Custom Exception을 사용합니다.
- Spring Security 도입 시 인증·권한 예외은 `AuthenticationEntryPoint`와 `AccessDeniedHandler`에서 공통 응답 형식으로 변환합니다.

```text
throw new ArticleNotFoundException(articleId);
```

## 3.7 API URL

Frontend가 호출하는 Spring Boot API는 `/api/v1`을 기본 경로로 사용합니다.
Controller에서는 `ApiPaths.API_V1`을 사용하고 URL에는 명사와 복수형을 사용합니다.

```text
GET    /api/v1/articles
GET    /api/v1/articles/{articleId}
POST   /api/v1/articles
PATCH  /api/v1/articles/{articleId}
DELETE /api/v1/articles/{articleId}
```

---

# 4. AI Backend - FastAPI

## 4.1 Python 기본 Convention

- PEP 8을 기준으로 작성합니다.
- 들여쓰기는 Space 4칸을 사용합니다.
- 함수와 변수는 `snake_case`를 사용합니다.
- 클래스는 `PascalCase`를 사용합니다.
- 상수는 `UPPER_SNAKE_CASE`를 사용합니다.
- 주요 함수에는 Type Hint를 작성합니다.

```python
MAX_RETRY_COUNT = 3


def get_article_embedding(article_text: str) -> list[float]:
    ...
```

## 4.2 Naming

| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| 변수 | snake_case | `article_list` |
| 함수 | snake_case | `extract_keywords()` |
| 클래스 | PascalCase | `RecommendationService` |
| 상수 | UPPER_SNAKE_CASE | `MODEL_NAME` |
| 파일 | snake_case | `router.py`, `service.py`, `schemas.py`, `repository.py` |

## 4.3 Directory Structure

도메인(기능)별로 폴더를 나눕니다. 각 도메인 폴더는 `router.py`(요청/응답), `schemas.py`(Pydantic 모델), `service.py`(핵심 로직), `repository.py`(Neo4j 등 데이터 접근)로 구성합니다. `config.py`, `database.py`, `dependencies.py`, `exceptions.py`는 여러 도메인이 함께 쓰는 전역 코드로 `app/` 바로 아래에 둡니다.

```text
app/
├── main.py
├── config.py             # 전역 설정
├── database.py           # Neo4j 드라이버/세션 등 공용 DB 연결
├── dependencies.py       # 전역 의존성 (내부 서비스 인증 등)
├── exceptions.py         # 전역 예외 처리
├── articles/             # 기사 분석 도메인
│   ├── router.py
│   ├── schemas.py
│   ├── service.py
│   └── repository.py
├── recommendations/      # 추천 도메인
│   ├── router.py
│   ├── schemas.py
│   ├── service.py
│   └── repository.py
├── ml/                   # AI 모델 관련 코드 (임베딩, 추출, 클러스터링 등)
│   ├── embedding/
│   ├── clustering/
│   └── extraction/
└── utils/
```

도메인이 늘어나면 위 패턴으로 새 도메인 폴더를 추가합니다. 모든 파일을 항상 다 채울 필요는 없고, 필요한 파일만 추가합니다.

## 4.4 Router

Router(`<domain>/router.py`)에서는 요청과 응답 처리만 담당합니다.

```text
# recommendations/router.py
@router.post("/recommendations/calculate")
async def calculate_recommendations(
    request: RecommendationCalculateRequest,
) -> RecommendationCalculateResponse:
    return service.calculate_recommendations(request)
```

모델 실행, 전처리 등의 핵심 로직은 같은 도메인의 `service.py` 또는 `ml` 계층에 분리합니다. Neo4j 쿼리처럼 순수 데이터 접근 코드는 `repository.py`에 분리합니다.

## 4.5 Schema

Pydantic Schema를 사용하여 요청/응답 타입을 명확히 정의합니다. 각 도메인 폴더의 `schemas.py`에 둡니다.

```text
# recommendations/schemas.py
class RecommendationCalculateRequest(BaseModel):
    user_id: int
    limit: int = 10
```

## 4.6 AI Model Convention

모델 관련 코드는 아래 단계를 가능한 한 분리합니다.

```text
load
preprocess
inference
postprocess
```

예시:

```python
def preprocess_article(text: str) -> str:
    ...


def create_embedding(text: str) -> list[float]:
    ...


def calculate_similarity(
    source_embedding: list[float],
    target_embedding: list[float],
) -> float:
    ...
```

- 모델 이름과 버전은 설정 파일 또는 환경 변수에서 관리합니다.
- threshold, top-k 등의 값은 코드에 직접 하드코딩하지 않습니다.
- 랜덤성을 사용하는 경우 seed를 명시합니다.
- 모델 출력값은 API 응답 전에 검증합니다.
- 실험 코드와 운영 API 코드를 분리합니다.

---

# 5. Database - MySQL

## 5.1 Naming

- 테이블명: `snake_case`
- 컬럼명: `snake_case`
- 테이블명은 복수형 또는 단수형 중 하나를 팀에서 정해 일관되게 사용합니다.
- 본 프로젝트에서는 **복수형 사용을 권장**합니다.

```text
users
articles
article_categories
user_article_histories
```

## 5.2 PK / FK

PK:

```text
id
```

FK:

```text
user_id
article_id
category_id
```

## 5.3 Time Column

공통 시간 컬럼:

```text
created_at
updated_at
deleted_at
```

## 5.4 Boolean

Boolean 성격의 컬럼은 의미가 드러나도록 작성합니다.

```text
is_active
is_deleted
has_thumbnail
```

## 5.5 Index

다음과 같은 컬럼은 조회 패턴을 확인한 후 인덱스를 고려합니다.

- JOIN에 자주 사용되는 FK
- WHERE 조건에 자주 사용되는 컬럼
- 정렬/검색에 자주 사용되는 컬럼

불필요한 인덱스 생성은 지양합니다.

---

# 6. Database - Neo4j

## 6.1 Node Label

Node Label은 PascalCase를 사용합니다.

```text
Article
Event
Company
Person
Keyword
Category
```

## 6.2 Relationship Type

Relationship는 `UPPER_SNAKE_CASE`를 사용합니다.

```text
MENTIONS
RELATED_TO
BELONGS_TO
INVOLVES
SIMILAR_TO
READ
INTERESTED_IN
```

예시:

```text
(:Article)-[:MENTIONS]->(:Company)
(:Article)-[:COVERS]->(:Event)
(:Event)-[:INVOLVES]->(:Company)
(:User)-[:READ]->(:Article)
```

## 6.3 Property

Property는 `camelCase` 사용을 권장합니다.

```text
articleId
publishedAt
createdAt
similarityScore
```

## 6.4 Node ID

Neo4j 내부 ID에 의존하지 않고 서비스에서 관리하는 고유 ID를 별도 Property로 둡니다.

```cypher
(:Article {
    articleId: "article-123",
    title: "...",
    publishedAt: datetime()
})
```

## 6.5 Cypher Query

키워드에 대문자를 사용하여 가독성을 높입니다.

```cypher
MATCH (a:Article)-[:MENTIONS]->(c:Company)
WHERE a.articleId = $articleId
RETURN c
```

문자열을 Query에 직접 삽입하지 않고 Parameter를 사용합니다.

```cypher
WHERE a.articleId = $articleId
```

지양:

```cypher
WHERE a.articleId = 'article-123'
```

## 6.6 Ontology

그래프 관계는 사전에 정의한 Ontology를 기준으로 생성합니다.

임의의 Relationship Type을 코드에서 동적으로 생성하지 않습니다.

---

# 7. Infra - Docker

## 7.1 기본 원칙

- 서비스별 Dockerfile을 분리합니다.
- `.dockerignore`를 반드시 작성합니다.
- 비밀 정보는 Dockerfile에 직접 작성하지 않습니다.
- 설정값은 환경 변수로 주입합니다.
- 운영 이미지에는 불필요한 개발 도구를 포함하지 않습니다.

## 7.2 Naming

Container/Service 이름은 lowercase와 hyphen 사용을 권장합니다.

```text
frontend
backend
ai-server
mysql
neo4j
nginx
```

## 7.3 Environment Variable

환경 변수는 `UPPER_SNAKE_CASE`로 작성합니다.

```text
MYSQL_HOST
MYSQL_PORT
MYSQL_DATABASE
NEO4J_URI
NEO4J_USERNAME
SPRING_PROFILES_ACTIVE
```

`.env` 파일은 Git에 커밋하지 않습니다.

```gitignore
.env
.env.*
```

단, 예시 파일은 관리할 수 있습니다.

```text
.env.example
```

---

# 8. Infra - Jenkins

## 8.1 Pipeline Stage

Pipeline Stage 이름은 역할이 명확하도록 작성합니다.

```text
Checkout
Build
Test
Docker Build
Deploy
Health Check
```

예시:

```text
stages {
    stage('Checkout') {
        steps {
            ...
        }
    }

    stage('Build') {
        steps {
            ...
        }
    }

    stage('Test') {
        steps {
            ...
        }
    }

    stage('Deploy') {
        steps {
            ...
        }
    }
}
```

## 8.2 Credential

아래 정보는 Jenkins Credential로 관리합니다.

```text
SSH Key
Docker Registry Credential
Database Password
API Key
JWT Secret
```

Jenkinsfile에 직접 작성하지 않습니다.

---

# 9. Infra - Nginx

## 9.1 Configuration

서비스별 설정 영역을 구분합니다.

```nginx
location / {
    proxy_pass http://frontend;
}

location /api/ {
    proxy_pass http://backend;
}

location /ai/ {
    proxy_pass http://ai-server;
}
```

## 9.2 기본 원칙

- upstream 이름은 Docker 서비스명과 가능한 한 동일하게 유지합니다.
- API 경로 규칙을 명확히 구분합니다.
- 변경 시 설정 문법을 확인한 뒤 Reload 합니다.

```bash
nginx -t
```

---

# 10. Formatting / Lint

팀원 간 코드 스타일 차이를 줄이기 위해 자동 포맷터와 Linter 사용을 권장합니다.

| 영역 | Tool |
| --- | --- |
| React | ESLint, Prettier |
| Spring Boot | Checkstyle 또는 Spotless |
| FastAPI | Ruff, Black |
| Python Type Check | mypy (선택) |

IDE에서 `Format on Save` 설정을 권장합니다.

---

# 11. Pull Request Checklist

PR 생성 전 다음 사항을 확인합니다.

- [ ] 프로젝트가 정상적으로 빌드되는가?
- [ ] 사용하지 않는 코드/import를 제거했는가?
- [ ] 변수와 함수명이 역할을 명확하게 표현하는가?
- [ ] 중복 코드가 없는가?
- [ ] 민감 정보가 포함되어 있지 않은가?
- [ ] API 변경 사항을 공유했는가?
- [ ] DB Schema 또는 Graph Ontology 변경 사항을 공유했는가?
- [ ] 필요한 테스트를 수행했는가?
- [ ] 관련 Issue를 연결했는가?

---

# 12. 팀 공통 핵심 규칙

프로젝트에서는 아래 규칙을 우선적으로 지킵니다.

1. **의미가 드러나는 이름을 사용한다.**
2. **Controller/Router에 비즈니스 로직을 작성하지 않는다.**
3. **API 요청/응답 DTO 또는 Schema를 명확히 분리한다.**
4. **React API 호출 로직은 UI 컴포넌트와 분리한다.**
5. **FastAPI의 AI 처리 로직은 Router와 분리한다.**
6. **Neo4j Relationship는 정의된 Ontology 내에서만 생성한다.**
7. **비밀번호, API Key 등 민감 정보는 환경 변수로 관리한다.**
8. **코드 스타일은 Formatter/Linter를 통해 자동화한다.**
9. **작은 단위로 Commit하고 PR을 통해 코드 리뷰한다.**
10. **새로운 규칙이 필요하면 팀원과 합의 후 본 문서를 수정한다.**
