import { Component, type ErrorInfo, type ReactNode } from "react";

type RenderErrorBoundaryProps = {
  children: ReactNode;
  fallback: (error: Error) => ReactNode;
  resetKey?: string;
};

type RenderErrorBoundaryState = {
  error: Error | null;
};

export class RenderErrorBoundary extends Component<
  RenderErrorBoundaryProps,
  RenderErrorBoundaryState
> {
  state: RenderErrorBoundaryState = {
    error: null,
  };

  static getDerivedStateFromError(error: Error): RenderErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("3D renderer failed", error, info.componentStack);
  }

  componentDidUpdate(previousProps: RenderErrorBoundaryProps) {
    if (previousProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return this.props.fallback(this.state.error);
    }

    return this.props.children;
  }
}
