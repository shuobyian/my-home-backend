import {
  BadRequestException,
  Inject,
  Injectable,
  forwardRef,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { MaterialService } from 'src/material/material.service';
import { ReadProductDto } from 'src/product/dto/read-product-dto';
import { Product } from 'src/product/entities/product.entity';
import { DataSource, Repository } from 'typeorm';

@Injectable()
export class ProductService {
  constructor(
    private dataSource: DataSource,
    @InjectRepository(Product) private readonly product: Repository<Product>,
    @Inject(forwardRef(() => MaterialService))
    private materialService: MaterialService,
  ) {}

  async login({ password }: { password: string }) {
    if (password !== process.env.PASSWORD) {
      throw new BadRequestException('비밀번호가 올바르지 않습니다.');
    }
    return '';
  }

  async createAll(products: ReadProductDto[]) {
    const prevProducts = await this.product.find();

    const nextProducts = products
      .map((item) =>
        prevProducts.find((prev) => prev.name === item.name)
          ? undefined
          : {
              name: item.name,
              level: item.level,
              craftingPrice: item.craftingPrice,
              tool: item.tool,
            },
      )
      .filter(Boolean);

    if (nextProducts.length < 1) {
      throw new BadRequestException('새로 추가할 물품이 없습니다.');
    }

    const _materials = products.flatMap((item) => ({
      name: item.name,
      materials: item.materials,
    }));

    const saveProducts = await Promise.all(
      nextProducts.map((product) =>
        this.product.save(this.product.create(product)),
      ),
    );

    await this.materialService.createAll(_materials, saveProducts);

    return nextProducts;
  }

  async findOne(product_id: number): Promise<ReadProductDto> {
    return this.product.findOne({
      where: { id: product_id },
      relations: { materials: true },
    });
  }

  async findAll(): Promise<ReadProductDto[]> {
    return this.product.find({ relations: { materials: true } });
  }
}
