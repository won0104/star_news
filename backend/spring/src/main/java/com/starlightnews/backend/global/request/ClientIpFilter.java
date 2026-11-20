package com.starlightnews.backend.global.request;

import java.io.IOException;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 요청한 클라이언트의 IP 를 정해 요청 속성으로 남긴다. 비로그인 요청의 횟수 제한 키로 쓴다.
 *
 * <p>운영에서는 호스트 nginx 가 {@code X-Real-IP: $remote_addr} 로 실제 접속 IP 를 덮어써 넘기고,
 * Spring 컨테이너는 127.0.0.1 에만 바인딩돼 nginx 를 거치지 않고는 닿을 수 없다. 그래서 그 헤더는
 * 클라이언트가 바꿀 수 없다. app.client-ip.header 에 그 헤더 이름을 적는다(prod 기본값 X-Real-IP).
 *
 * <p>{@code request.getRemoteAddr()} 를 그대로 쓰지 않는 이유: prod 는
 * server.forward-headers-strategy=framework 라 remoteAddr 가 X-Forwarded-For 의 맨 앞 값으로 바뀐다.
 * nginx 는 X-Forwarded-For 에 받은 값을 이어 붙이므로($proxy_add_x_forwarded_for) 맨 앞 값은
 * 클라이언트가 마음대로 적은 값이다. 그걸 키로 쓰면 요청마다 IP 를 바꿔 제한을 피할 수 있다.
 *
 * <p>헤더를 설정하지 않았거나(로컬) 헤더가 비어 있으면 remoteAddr 를 쓴다.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 1)
public class ClientIpFilter extends OncePerRequestFilter {

	public static final String ATTRIBUTE_NAME = "starlightNews.clientIp";

	/** IPv6 문자열 최대 길이(45)에 여유를 둔 값. 이보다 길면 IP 가 아니므로 믿지 않는다. */
	private static final int MAX_IP_LENGTH = 64;

	private final String trustedHeader;

	public ClientIpFilter(@Value("${app.client-ip.header:}") String trustedHeader) {
		this.trustedHeader = trustedHeader == null ? "" : trustedHeader.strip();
	}

	@Override
	protected void doFilterInternal(
			HttpServletRequest request,
			HttpServletResponse response,
			FilterChain filterChain
	) throws ServletException, IOException {
		request.setAttribute(ATTRIBUTE_NAME, resolve(request));
		filterChain.doFilter(request, response);
	}

	String resolve(HttpServletRequest request) {
		if (!trustedHeader.isEmpty()) {
			String value = request.getHeader(trustedHeader);
			if (StringUtils.hasText(value) && value.strip().length() <= MAX_IP_LENGTH) {
				return value.strip();
			}
		}
		return request.getRemoteAddr();
	}
}
