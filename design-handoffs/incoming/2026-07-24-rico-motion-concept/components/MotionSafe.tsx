/**
 * MotionSafe — one place to read the motion preference.
 *
 * Wrap a subtree once; children call `useMotionSafe()` to learn whether motion
 * is allowed. Honestly gates every animated component in this kit.
 */
"use client";
import React, { createContext, useContext } from "react";
import { useReducedMotion } from "./hooks";

interface MotionState {
    /** true when motion should be suppressed. */
    reduced: boolean;
}

const MotionCtx = createContext<MotionState>({ reduced: false });

export function MotionSafe({ children }: { children: React.ReactNode }) {
    const reduced = useReducedMotion();
    return <MotionCtx.Provider value={{ reduced }}>{children}</MotionCtx.Provider>;
}

export function useMotionSafe(): MotionState {
    return useContext(MotionCtx);
}
