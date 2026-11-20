# ==============================
# 1. Spring Boot Build
# ==============================
FROM eclipse-temurin:21-jdk AS builder

WORKDIR /app

COPY . .

RUN chmod +x gradlew
RUN ./gradlew clean bootJar --no-daemon


# ==============================
# 2. Spring Boot Runtime
# ==============================
# 21.0.13.1 이상으로 고정해야 아래 Base64 우회 플래그를 뗄 수 있다. 2026-11-20 기준 Docker Hub 에
# 21.0.13.1 태그가 없어(최신 21.0.13_9) 아직 21-jre 를 따라간다.
FROM eclipse-temurin:21-jre

WORKDIR /app

COPY --from=builder /app/build/libs/*.jar app.jar

EXPOSE 8080

# -XX:-UseBASE64Intrinsics: CVE-2026-114938(Java4Shell) 임시 우회.
#   AVX-512 VBMI 를 지원하는 x86-64 CPU 에서 JIT 가 쓰는 Base64 디코더 intrinsic 에 결함이 있다.
#   이 서버는 공개 API 의 커서를 java.util.Base64 URL 디코더로 풀기 때문에, 사용자가 보낸 값이
#   그대로 결함 있는 경로를 탄다. intrinsic 을 끄면 순수 Java 구현으로 디코딩해 결함을 피한다.
#   커서 디코딩은 요청당 수십 바이트라 성능 차이는 무시할 만하다.
#   제거 시점: 런타임 이미지가 Java 21.0.13.1 이상(예: eclipse-temurin:21.0.13.1_x-jre)으로
#   고정되거나 21-jre 가 그 버전을 가리키는 것을 확인한 뒤.
ENTRYPOINT ["java", "-XX:-UseBASE64Intrinsics", "-Duser.timezone=Asia/Seoul", "-jar", "app.jar"]
