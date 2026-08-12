"use client";

import { useState, useCallback } from "react";
import type { ProductResult, CartOut, CartLine } from "@/lib/api";
import { cartApi } from "@/lib/api";

export interface CartItem {
  product: ProductResult;
  quantity: number;
  /** Set only for products sourced from outside our catalog, so the cart can
      offer a link to the retailer's own page. */
  seller?: string | null;
  productUrl?: string | null;
}

interface UseCartReturn {
  items: CartItem[];
  addItem: (product: ProductResult, quantity?: number) => void;
  removeItem: (productId: number) => void;
  updateQty: (productId: number, quantity: number) => void;
  clearCart: () => void;
  refresh: () => void;
  applyServerCart: (cart: CartOut) => void;
  subtotal: number;
  tax: number;
  total: number;
  isEmpty: boolean;
}

// A server cart line rendered as the {product, quantity} shape the UI expects.
//
// The cart API returns no category or stock, so those stay empty here. The
// image_url it does return is carried through: the drawer used to ignore it and
// draw the same generic trolley icon on every line, which made a five-item cart
// look like five copies of one thing.
function lineToItem(line: CartLine): CartItem {
  return {
    product: {
      id: line.item_id,
      name: line.name,
      category: line.category ?? "",
      description: line.description ?? null,
      unit: line.unit,
      price_per_unit: line.unit_price,
      stock: 0,
      image_url: line.image_url,
      similarity: 0,
    },
    quantity: line.quantity,
    seller: line.seller ?? null,
    productUrl: line.product_url ?? null,
  };
}

/**
 * Server-backed cart. The `cart_items` table (keyed by session) is the source of
 * truth; every mutation calls the API and the returned CartOut replaces local
 * state. Chat/voice replies also carry the cart, applied via `applyServerCart`,
 * so "add item 2" updates the same badge as the "+ Add" button.
 */
export function useCart(sessionId: string): UseCartReturn {
  const [cart, setCart] = useState<CartOut | null>(null);

  const applyServerCart = useCallback((next: CartOut) => setCart(next), []);

  const refresh = useCallback(() => {
    if (!sessionId) return;
    cartApi.get(sessionId).then(setCart).catch(() => {});
  }, [sessionId]);

  const addItem = useCallback((product: ProductResult, quantity = 1) => {
    if (!sessionId) return;
    cartApi.add(sessionId, product.id, quantity).then(setCart).catch(() => {});
  }, [sessionId]);

  const removeItem = useCallback((productId: number) => {
    if (!sessionId) return;
    cartApi.remove(sessionId, productId).then(setCart).catch(() => {});
  }, [sessionId]);

  const updateQty = useCallback((productId: number, quantity: number) => {
    if (!sessionId) return;
    cartApi.setQuantity(sessionId, productId, quantity).then(setCart).catch(() => {});
  }, [sessionId]);

  const clearCart = useCallback(() => {
    if (!sessionId) { setCart(null); return; }
    cartApi.clear(sessionId).then(setCart).catch(() => setCart(null));
  }, [sessionId]);

  const items = (cart?.items ?? []).map(lineToItem);

  return {
    items,
    addItem,
    removeItem,
    updateQty,
    clearCart,
    refresh,
    applyServerCart,
    subtotal: cart?.subtotal ?? cart?.total ?? 0,
    tax: cart?.tax ?? 0,
    total: cart?.total ?? 0,
    isEmpty: items.length === 0,
  };
}
