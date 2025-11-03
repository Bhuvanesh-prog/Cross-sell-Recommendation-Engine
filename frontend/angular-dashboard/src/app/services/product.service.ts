import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface ProductPayload {
  product_id: string;
  name: string;
  category: string;
  subcategory?: string;
  brand?: string;
  base_price?: number;
}

export interface RecommendationResponse {
  product_id: string;
  recommendations: Array<Record<string, unknown>>;
}

@Injectable({ providedIn: 'root' })
export class ProductService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  listProducts(): Observable<ProductPayload[]> {
    return this.http.get<ProductPayload[]>(`${this.baseUrl}/api/products`);
  }

  createProduct(payload: ProductPayload): Observable<ProductPayload> {
    return this.http.post<ProductPayload>(`${this.baseUrl}/api/products`, payload);
  }

  recommendations(productId: string, limit = 5): Observable<RecommendationResponse> {
    return this.http.get<RecommendationResponse>(
      `${this.baseUrl}/api/recommendations/${encodeURIComponent(productId)}`,
      { params: { limit } }
    );
  }
}
