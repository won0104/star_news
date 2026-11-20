package com.starlightnews.backend.global.config;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import net.javacrumbs.shedlock.spring.annotation.SchedulerLock;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.context.annotation.ClassPathScanningCandidateComponentProvider;
import org.springframework.core.type.filter.AnnotationTypeFilter;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.util.ClassUtils;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 새 배치가 잠금 없이 추가되지 않게 막는다.
 *
 * <p>{@code @SchedulerLock} 을 빠뜨리면 컴파일도 기동도 멀쩡하고, 인스턴스를 두 대 띄운 뒤에야 배치가
 * 두 번 도는 것으로 드러난다. 이름이 겹치면 서로 다른 배치가 한 잠금을 나눠 써 한쪽이 건너뛰어진다.
 */
class SchedulerLockCoverageTest {

	@Test
	void 모든_스케줄_배치에_서로_다른_이름의_잠금이_걸려_있다() throws ClassNotFoundException {
		List<Method> scheduled = scheduledMethods();
		assertThat(scheduled).as("스캔이 비면 이 테스트가 아무것도 확인하지 못한다").hasSizeGreaterThanOrEqualTo(8);

		Set<String> names = new HashSet<>();
		for (Method method : scheduled) {
			SchedulerLock lock = method.getAnnotation(SchedulerLock.class);
			String where = method.getDeclaringClass().getSimpleName() + "." + method.getName();
			assertThat(lock).as(where + " 에 @SchedulerLock 이 없다").isNotNull();
			assertThat(lock.name()).as(where + " 잠금 이름").isNotBlank();
			assertThat(lock.lockAtMostFor()).as(where + " lockAtMostFor").isNotBlank();
			assertThat(names.add(lock.name())).as(where + " 잠금 이름이 겹친다: " + lock.name()).isTrue();
		}
	}

	private List<Method> scheduledMethods() throws ClassNotFoundException {
		ClassPathScanningCandidateComponentProvider scanner = new ClassPathScanningCandidateComponentProvider(false);
		scanner.addIncludeFilter(new AnnotationTypeFilter(Component.class));

		List<Method> methods = new ArrayList<>();
		for (BeanDefinition candidate : scanner.findCandidateComponents("com.starlightnews.backend")) {
			Class<?> type = ClassUtils.forName(candidate.getBeanClassName(), getClass().getClassLoader());
			for (Method method : type.getDeclaredMethods()) {
				if (method.isAnnotationPresent(Scheduled.class)) {
					methods.add(method);
				}
			}
		}
		return methods;
	}
}
