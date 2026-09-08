package com.starlightnews.backend.domain.user.repository;

import java.util.Optional;

import com.starlightnews.backend.domain.user.domain.User;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserRepository extends JpaRepository<User, Long> {

	boolean existsByLoginId(String loginId);

	Optional<User> findByLoginId(String loginId);
}
