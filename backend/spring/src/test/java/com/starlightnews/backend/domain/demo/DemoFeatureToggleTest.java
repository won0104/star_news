package com.starlightnews.backend.domain.demo;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisRecorder;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalyzeClient;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.service.ArticleWriter;
import com.starlightnews.backend.domain.demo.controller.DemoArticleController;
import com.starlightnews.backend.domain.demo.repository.DemoGraphRepository;
import com.starlightnews.backend.domain.demo.repository.Neo4jDemoGraphRepository;
import com.starlightnews.backend.domain.demo.service.DemoArticleService;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.data.neo4j.core.Neo4jClient;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

/**
 * 시연 기능 스위치(app.demo.enabled)가 컨트롤러·서비스·저장소를 함께 켜고 끄는지 확인한다.
 * 기사 투입 경로가 운영에 실수로 열리지 않게 하는 것이 목적이다.
 */
class DemoFeatureToggleTest {

	private final ApplicationContextRunner runner = new ApplicationContextRunner()
			.withBean(ArticleWriter.class, () -> mock(ArticleWriter.class))
			.withBean(ArticleRepository.class, () -> mock(ArticleRepository.class))
			.withBean(ArticleAnalyzeClient.class, () -> mock(ArticleAnalyzeClient.class))
			.withBean(ArticleAnalysisRecorder.class, () -> mock(ArticleAnalysisRecorder.class))
			.withBean(Neo4jClient.class, () -> mock(Neo4jClient.class))
			.withUserConfiguration(
					DemoArticleController.class,
					DemoArticleService.class,
					Neo4jDemoGraphRepository.class);

	@Test
	void 설정이_없으면_시연_빈을_만들지_않는다() {
		runner.run(context -> {
			assertThat(context).hasNotFailed();
			assertThat(context).doesNotHaveBean(DemoArticleController.class);
			assertThat(context).doesNotHaveBean(DemoArticleService.class);
			assertThat(context).doesNotHaveBean(DemoGraphRepository.class);
		});
	}

	@Test
	void 꺼져_있으면_시연_빈을_만들지_않는다() {
		runner.withPropertyValues("app.demo.enabled=false").run(context -> {
			assertThat(context).hasNotFailed();
			assertThat(context).doesNotHaveBean(DemoArticleController.class);
		});
	}

	@Test
	void 켜면_시연_빈을_모두_만든다() {
		runner.withPropertyValues("app.demo.enabled=true").run(context -> {
			assertThat(context).hasNotFailed();
			assertThat(context).hasSingleBean(DemoArticleController.class);
			assertThat(context).hasSingleBean(DemoArticleService.class);
			assertThat(context).hasSingleBean(DemoGraphRepository.class);
		});
	}
}
