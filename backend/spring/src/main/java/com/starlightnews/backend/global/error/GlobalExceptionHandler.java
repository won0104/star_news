package com.starlightnews.backend.global.error;

import java.util.List;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.MethodParameter;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.ServletRequestBindingException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

	@ExceptionHandler(BusinessException.class)
	public ResponseEntity<ErrorResponse> handleBusinessException(
			BusinessException exception,
			HttpServletRequest request
	) {
		ErrorCode errorCode = exception.getErrorCode();
		log.debug("Business exception: code={}, path={}", errorCode.getCode(), request.getRequestURI());
		return createResponse(errorCode, request);
	}

	@ExceptionHandler(MethodArgumentNotValidException.class)
	public ResponseEntity<ErrorResponse> handleMethodArgumentNotValidException(
			MethodArgumentNotValidException exception,
			HttpServletRequest request
	) {
		List<FieldErrorResponse> errors = exception.getBindingResult()
				.getFieldErrors()
				.stream()
				.map(error -> new FieldErrorResponse(error.getField(), error.getDefaultMessage()))
				.toList();

		return createResponse(ErrorCode.INVALID_INPUT_VALUE, request, errors);
	}

	@ExceptionHandler(HandlerMethodValidationException.class)
	public ResponseEntity<ErrorResponse> handleHandlerMethodValidationException(
			HandlerMethodValidationException exception,
			HttpServletRequest request
	) {
		List<FieldErrorResponse> errors = exception.getParameterValidationResults()
				.stream()
				.flatMap(result -> result.getResolvableErrors()
						.stream()
						.map(error -> new FieldErrorResponse(
								resolveParameterName(result.getMethodParameter()),
								error.getDefaultMessage()
						)))
				.toList();

		return createResponse(ErrorCode.INVALID_INPUT_VALUE, request, errors);
	}

	@ExceptionHandler(ConstraintViolationException.class)
	public ResponseEntity<ErrorResponse> handleConstraintViolationException(
			ConstraintViolationException exception,
			HttpServletRequest request
	) {
		List<FieldErrorResponse> errors = exception.getConstraintViolations()
				.stream()
				.map(violation -> new FieldErrorResponse(
						violation.getPropertyPath().toString(),
						violation.getMessage()
				))
				.toList();

		return createResponse(ErrorCode.INVALID_INPUT_VALUE, request, errors);
	}

	@ExceptionHandler(MethodArgumentTypeMismatchException.class)
	public ResponseEntity<ErrorResponse> handleMethodArgumentTypeMismatchException(
			MethodArgumentTypeMismatchException exception,
			HttpServletRequest request
	) {
		List<FieldErrorResponse> errors = List.of(
				new FieldErrorResponse(exception.getName(), ErrorCode.TYPE_MISMATCH.getMessage())
		);
		return createResponse(ErrorCode.TYPE_MISMATCH, request, errors);
	}

	@ExceptionHandler(HttpMessageNotReadableException.class)
	public ResponseEntity<ErrorResponse> handleHttpMessageNotReadableException(
			HttpMessageNotReadableException exception,
			HttpServletRequest request
	) {
		return createResponse(ErrorCode.MALFORMED_REQUEST, request);
	}

	@ExceptionHandler(ServletRequestBindingException.class)
	public ResponseEntity<ErrorResponse> handleServletRequestBindingException(
			ServletRequestBindingException exception,
			HttpServletRequest request
	) {
		return createResponse(ErrorCode.MISSING_REQUIRED_VALUE, request);
	}

	@ExceptionHandler(NoResourceFoundException.class)
	public ResponseEntity<ErrorResponse> handleNoResourceFoundException(
			NoResourceFoundException exception,
			HttpServletRequest request
	) {
		return createResponse(ErrorCode.RESOURCE_NOT_FOUND, request);
	}

	@ExceptionHandler(HttpRequestMethodNotSupportedException.class)
	public ResponseEntity<ErrorResponse> handleHttpRequestMethodNotSupportedException(
			HttpRequestMethodNotSupportedException exception,
			HttpServletRequest request
	) {
		return createResponse(ErrorCode.METHOD_NOT_ALLOWED, request);
	}

	@ExceptionHandler(HttpMediaTypeNotSupportedException.class)
	public ResponseEntity<ErrorResponse> handleHttpMediaTypeNotSupportedException(
			HttpMediaTypeNotSupportedException exception,
			HttpServletRequest request
	) {
		return createResponse(ErrorCode.UNSUPPORTED_MEDIA_TYPE, request);
	}

	@ExceptionHandler(Exception.class)
	public ResponseEntity<ErrorResponse> handleException(
			Exception exception,
			HttpServletRequest request
	) {
		log.error("Unhandled exception: path={}", request.getRequestURI(), exception);
		return createResponse(ErrorCode.INTERNAL_SERVER_ERROR, request);
	}

	private ResponseEntity<ErrorResponse> createResponse(
			ErrorCode errorCode,
			HttpServletRequest request
	) {
		return createResponse(errorCode, request, List.of());
	}

	private ResponseEntity<ErrorResponse> createResponse(
			ErrorCode errorCode,
			HttpServletRequest request,
			List<FieldErrorResponse> errors
	) {
		ErrorResponse response = ErrorResponse.of(errorCode, request.getRequestURI(), errors);
		return ResponseEntity.status(errorCode.getStatus()).body(response);
	}

	private String resolveParameterName(MethodParameter parameter) {
		return parameter.getParameterName() != null
				? parameter.getParameterName()
				: "argument" + parameter.getParameterIndex();
	}
}
