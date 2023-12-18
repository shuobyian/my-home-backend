import {
  BadRequestException,
  Inject,
  Injectable,
  forwardRef,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { MaterialService } from 'src/material/material.service';
import { ReadProductDto } from 'src/product/dto/read-product-dto';
import { UpdateProductDto } from 'src/product/dto/update-product-dto';
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

  async create({ materials, ...product }: ReadProductDto) {
    const prevProduct = await this.product.find({ where: { id: product.id } });

    if (prevProduct) {
      throw new BadRequestException('이미 추가된 물품입니다.');
    }

    const saveProduct = await this.product.save(this.product.create(product));

    await Promise.all(
      materials.map((material) =>
        this.materialService.create(material, product.id),
      ),
    );

    return saveProduct;
  }

  async update({ materials, ...product }: UpdateProductDto) {
    await this.materialService.delete(product.id);

    await Promise.all(
      materials.map((material) =>
        this.materialService.create(material, product.id),
      ),
    );

    return this.product.save(product);
  }

  delete(ids: number[]) {
    return Promise.all(ids.map((id) => this.product.delete({ id })));
  }

  findOne(product_id: number): Promise<ReadProductDto> {
    return this.product.findOne({
      where: { id: product_id },
      relations: { materials: true },
    });
  }

  findAll(): Promise<ReadProductDto[]> {
    return this.product.find({ relations: { materials: true } });
  }

  async findAllPage(page: number, size: number) {
    const [products, totalElements] = await this.product.findAndCount({
      relations: { materials: true },
      order: { id: 'ASC' },
      take: size,
      skip: page * size,
    });

    return {
      totalElements,
      content: products,
    };
  }
}
