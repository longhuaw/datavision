/// <reference types="vite/client" />

declare module '*.module.css' {
  const classes: { readonly [key: string]: string };
  export default classes;
}

declare module '*.module.scss' {
  const classes: { readonly [key: string]: string };
  export default classes;
}

declare module 'react-grid-layout' {
  import { Component } from 'react';

  export interface Layout {
    i: string;
    x: number;
    y: number;
    w: number;
    h: number;
    minW?: number;
    minH?: number;
    maxW?: number;
    maxH?: number;
    static?: boolean;
    isDraggable?: boolean;
    isResizable?: boolean;
  }

  export interface ReactGridLayoutProps {
    className?: string;
    style?: React.CSSProperties;
    layout?: Layout[];
    cols?: number;
    rowHeight?: number;
    width?: number;
    autoSize?: boolean;
    margin?: [number, number];
    containerPadding?: [number, number];
    isDraggable?: boolean;
    isResizable?: boolean;
    compactType?: 'vertical' | 'horizontal' | null;
    onLayoutChange?: (layout: Layout[]) => void;
    onDragStart?: (layout: Layout[], oldItem: Layout, newItem: Layout) => void;
    onDrag?: (layout: Layout[], oldItem: Layout, newItem: Layout) => void;
    onDragStop?: (layout: Layout[], oldItem: Layout, newItem: Layout) => void;
    onResizeStart?: (layout: Layout[], oldItem: Layout, newItem: Layout) => void;
    onResize?: (layout: Layout[], oldItem: Layout, newItem: Layout) => void;
    onResizeStop?: (layout: Layout[], oldItem: Layout, newItem: Layout) => void;
    children?: React.ReactNode;
  }

  export default class ReactGridLayout extends Component<ReactGridLayoutProps> {}
  export class Responsive extends Component<any> {}
  export function WidthProvider(component: any): any;
}
