"use client";
import { Component, ReactNode } from "react";

interface Props { children: ReactNode }
interface State { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex items-center justify-center min-h-[60vh] p-6">
          <div
            className="rounded-xl p-6 max-w-lg w-full"
            style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)" }}
          >
            <p className="font-semibold text-sm mb-2" style={{ color: "#ef4444" }}>
              Erreur sur cette page
            </p>
            <p className="text-xs font-mono" style={{ color: "#fca5a5" }}>
              {this.state.error.message}
            </p>
            <button
              onClick={() => this.setState({ error: null })}
              className="mt-4 px-4 py-2 rounded-lg text-xs font-medium"
              style={{ background: "rgba(239,68,68,0.15)", color: "#ef4444" }}
            >
              Réessayer
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
