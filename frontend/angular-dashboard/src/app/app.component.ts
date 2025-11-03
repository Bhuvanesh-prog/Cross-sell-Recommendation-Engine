import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ProductPayload, ProductService } from './services/product.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit {
  title = 'Cross-Sell Recommendation Dashboard';
  loading = false;
  error?: string;
  success?: string;
  products: ProductPayload[] = [];
  recommendations: Array<Record<string, unknown>> = [];
  selectedProductId?: string;

  readonly productForm = this.fb.nonNullable.group({
    product_id: ['', [Validators.required, Validators.maxLength(64)]],
    name: ['', [Validators.required, Validators.maxLength(256)]],
    category: ['', [Validators.required, Validators.maxLength(256)]],
    subcategory: ['', [Validators.maxLength(256)]],
    brand: ['', [Validators.maxLength(256)]],
    base_price: [0, [Validators.min(0)]],
  });

  constructor(private readonly fb: FormBuilder, private readonly productService: ProductService) {}

  ngOnInit(): void {
    this.refreshProducts();
  }

  refreshProducts(selectId?: string): void {
    this.productService.listProducts().subscribe({
      next: (products) => {
        this.products = products;
        if (selectId) {
          this.fetchRecommendations(selectId);
        }
      },
      error: (err) => this.handleError(err)
    });
  }

  submit(): void {
    if (this.productForm.invalid) {
      this.productForm.markAllAsTouched();
      return;
    }

    this.loading = true;
    this.error = undefined;
    this.success = undefined;

    const payload = { ...this.productForm.getRawValue() };
    payload.base_price = Number(payload.base_price ?? 0);

    this.productService.createProduct(payload).subscribe({
      next: (product) => {
        this.success = `Saved product ${product.name}`;
        this.selectedProductId = product.product_id;
        this.productForm.reset({ base_price: 0 });
        this.refreshProducts(product.product_id);
        this.fetchRecommendations(product.product_id);
      },
      error: (err) => this.handleError(err),
      complete: () => {
        this.loading = false;
      }
    });
  }

  selectProduct(productId: string): void {
    this.selectedProductId = productId;
    this.fetchRecommendations(productId);
  }

  fetchRecommendations(productId: string): void {
    if (!productId) {
      this.recommendations = [];
      return;
    }
    this.productService.recommendations(productId).subscribe({
      next: (response) => {
        this.recommendations = response.recommendations ?? [];
      },
      error: (err) => this.handleError(err)
    });
  }

  private handleError(err: unknown): void {
    console.error(err);
    this.loading = false;
    this.success = undefined;
    this.error = 'Unable to complete the request. Ensure the API is running and the lakehouse gold data exists.';
  }
}
